// 原QRS检测器的启动学习候选；原版独立保留，不改既有smoke。
// 使用一阶差分绝对值、滑动积分、自适应阈值和不应期。
// 本模块不替代临床设备；参数需要根据实际采样率、幅值和参考标注校准。
module ecg_qrs_auto #(
    // 输入采样位宽、采样率、积分窗口和不应期时长。
    parameter integer SAMPLE_WIDTH = 16,
    parameter integer SAMPLE_RATE_HZ = 360,
    parameter integer INTEGRATION_MS = 120,
    parameter integer REFRACTORY_MS = 200,
    // 积分能量位宽，以及自适应阈值的初始噪声/信号估计值。
    parameter integer ENERGY_WIDTH = 24,
    parameter integer INITIAL_NOISE_LEVEL = 4096,
    parameter integer INITIAL_SIGNAL_LEVEL = 16384,
    parameter integer BOOTSTRAP_SECONDS = 2
) (
    // sample_valid 拉高时采入一个 sample_in。
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         sample_valid,
    input  logic signed [SAMPLE_WIDTH-1:0] sample_in,
    // qrs_valid 为单周期脉冲；RR 间期以采样点数表示。
    // qrs_sample_index 是积分窗口回移后的近似采样位置。
    output logic                         qrs_valid,
    output logic [31:0]                  qrs_sample_index,
    output logic [31:0]                  rr_interval_samples,
    // 下列信号用于调试和后续质量评估。
    output logic [ENERGY_WIDTH-1:0]      integrated_energy,
    output logic [ENERGY_WIDTH-1:0]      adaptive_threshold
);

    // 根据采样率和毫秒参数换算滑动积分窗口长度与不应期长度。
    localparam integer RAW_WINDOW_LENGTH =
        (SAMPLE_RATE_HZ * INTEGRATION_MS) / 1000;
    localparam integer WINDOW_LENGTH =
        (RAW_WINDOW_LENGTH < 1) ? 1 : RAW_WINDOW_LENGTH;
    localparam integer RAW_REFRACTORY_LENGTH =
        (SAMPLE_RATE_HZ * REFRACTORY_MS) / 1000;
    localparam integer REFRACTORY_LENGTH =
        (RAW_REFRACTORY_LENGTH < 1) ? 1 : RAW_REFRACTORY_LENGTH;
    localparam integer POINTER_WIDTH =
        (WINDOW_LENGTH <= 1) ? 1 : $clog2(WINDOW_LENGTH);
    localparam integer WINDOW_CENTER = WINDOW_LENGTH / 2;

    logic signed [SAMPLE_WIDTH-1:0] previous_sample;
    logic                         previous_sample_valid;
    logic [SAMPLE_WIDTH:0]        derivative_history [0:WINDOW_LENGTH-1];
    logic [POINTER_WIDTH-1:0]     write_pointer;
    logic [31:0]                  sample_index;
    logic [31:0]                  last_qrs_index;
    logic                         have_last_qrs;
    logic [31:0]                  refractory_remaining;
    logic [ENERGY_WIDTH-1:0]      noise_level;
    logic [ENERGY_WIDTH-1:0]      signal_level;
    logic [ENERGY_WIDTH-1:0]      previous_energy;

    // 以完整积分窗的启动能量均值/最大值初始化，保持原输入码域。
    localparam integer BOOTSTRAP_LENGTH = SAMPLE_RATE_HZ * BOOTSTRAP_SECONDS;
    localparam integer BOOTSTRAP_WINDOWS = BOOTSTRAP_LENGTH - WINDOW_LENGTH;
    logic [31:0] bootstrap_sum;
    logic [ENERGY_WIDTH-1:0] older_energy;
    logic [ENERGY_WIDTH-1:0] bootstrap_peak;
    logic [ENERGY_WIDTH-1:0] energy_next;
    // 固定点倒数乘法替代64位组合除法；当前360/500Hz配置总和小于2^32。
    localparam logic [63:0] BOOTSTRAP_RECIPROCAL = 64'h100000000 / BOOTSTRAP_WINDOWS;
    wire [31:0] bootstrap_total = bootstrap_sum + energy_next;
    // 启动结束后分三拍计算；持续接收样本并保留位置，ready前不输出事件。
    logic [31:0] bootstrap_latched_sum;
    logic [ENERGY_WIDTH-1:0] bootstrap_latched_peak;
    logic [47:0] bootstrap_product_low, bootstrap_product_high;
    logic [63:0] bootstrap_product;
    logic [1:0] bootstrap_phase;
    logic bootstrap_ready;
    wire [31:0] bootstrap_mean = bootstrap_product[63:32];
    wire [ENERGY_WIDTH-1:0] bootstrap_noise = (bootstrap_mean < 1) ? 1 : bootstrap_mean;
    wire [ENERGY_WIDTH-1:0] bootstrap_max = (bootstrap_peak > energy_next) ? bootstrap_peak : energy_next;
    initial begin
        if ((SAMPLE_WIDTH != 16) || (ENERGY_WIDTH != 24) ||
            ((SAMPLE_RATE_HZ != 360) && (SAMPLE_RATE_HZ != 500)) ||
            (INTEGRATION_MS != 120) || (REFRACTORY_MS != 200) || (BOOTSTRAP_SECONDS != 2))
            $error("Candidate only supports reviewed 360/500Hz configuration");
    end

    logic signed [SAMPLE_WIDTH:0] derivative;
    logic [SAMPLE_WIDTH:0]        absolute_derivative;
    logic [ENERGY_WIDTH-1:0]      derivative_term;
    logic [ENERGY_WIDTH-1:0]      threshold_next;
    logic [31:0]                  corrected_sample_index;
    integer                       reset_index;

    always_comb begin
        corrected_sample_index = (sample_index >= WINDOW_CENTER)
                               ? sample_index - WINDOW_CENTER : 0;
        // 计算相邻样本差分的绝对值，作为当前积分窗口的新输入。
        derivative = $signed({sample_in[SAMPLE_WIDTH-1], sample_in})
                   - $signed({previous_sample[SAMPLE_WIDTH-1], previous_sample});

        if (derivative[SAMPLE_WIDTH]) begin
            absolute_derivative = (~derivative) + {{SAMPLE_WIDTH{1'b0}}, 1'b1};
        end else begin
            absolute_derivative = derivative[SAMPLE_WIDTH:0];
        end

        derivative_term = absolute_derivative;
        // 用新差分替换循环缓冲区中最旧的一项，得到滑动积分值。
        energy_next = integrated_energy
                    - derivative_history[write_pointer]
                    + derivative_term;

        // 在噪声估计和信号估计之间生成自适应阈值。
        if (signal_level > noise_level) begin
            threshold_next = noise_level + ((signal_level - noise_level) >> 2);
        end else begin
            threshold_next = noise_level;
        end

        if (threshold_next == '0) begin
            threshold_next = {{(ENERGY_WIDTH-1){1'b0}}, 1'b1};
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            // 复位状态、计数器和积分窗口缓存。
            bootstrap_sum <= '0;
            bootstrap_latched_sum <= '0;
            bootstrap_latched_peak <= '0;
            bootstrap_product_low <= '0;
            bootstrap_product_high <= '0;
            bootstrap_product <= '0;
            bootstrap_phase <= '0;
            bootstrap_ready <= 1'b0;
            older_energy <= '0;
            bootstrap_peak <= '0;
            previous_sample       <= '0;
            previous_sample_valid <= 1'b0;
            write_pointer         <= '0;
            sample_index          <= '0;
            last_qrs_index        <= '0;
            have_last_qrs         <= 1'b0;
            refractory_remaining  <= '0;
            integrated_energy     <= '0;
            previous_energy       <= '0;
            noise_level           <= INITIAL_NOISE_LEVEL;
            signal_level          <= INITIAL_SIGNAL_LEVEL;
            adaptive_threshold    <= INITIAL_NOISE_LEVEL
                                   + ((INITIAL_SIGNAL_LEVEL - INITIAL_NOISE_LEVEL) >> 2);
            qrs_valid             <= 1'b0;
            qrs_sample_index      <= '0;
            rr_interval_samples   <= '0;

            for (reset_index = 0; reset_index < WINDOW_LENGTH; reset_index = reset_index + 1) begin
                derivative_history[reset_index] <= '0;
            end
        end else begin
            qrs_valid <= 1'b0;
            adaptive_threshold <= threshold_next;
            case (bootstrap_phase)
                1: begin
                    bootstrap_product_low <= bootstrap_latched_sum[15:0] * BOOTSTRAP_RECIPROCAL[31:0];
                    bootstrap_product_high <= bootstrap_latched_sum[31:16] * BOOTSTRAP_RECIPROCAL[31:0];
                    bootstrap_phase <= 2;
                end
                2: begin
                    bootstrap_product <= {16'b0, bootstrap_product_low}
                                       + {bootstrap_product_high, 16'b0};
                    bootstrap_phase <= 3;
                end
                3: begin
                    noise_level <= bootstrap_noise;
                    signal_level <= (bootstrap_latched_peak > bootstrap_noise)
                                  ? bootstrap_latched_peak : bootstrap_noise + 1'b1;
                    bootstrap_ready <= 1'b1;
                    bootstrap_phase <= 0;
                end
                default: ;
            endcase

            if (sample_valid) begin
                sample_index <= sample_index + 1'b1;
                previous_sample <= sample_in;

                if (!previous_sample_valid) begin
                    previous_sample_valid <= 1'b1;
                end else begin
                    // 更新积分窗口和采样位置计数。
                    derivative_history[write_pointer] <= absolute_derivative;
                    integrated_energy <= energy_next;
                    previous_energy <= energy_next;
                    older_energy <= previous_energy;

                    if (write_pointer == WINDOW_LENGTH - 1) begin
                        write_pointer <= '0;
                    end else begin
                        write_pointer <= write_pointer + 1'b1;
                    end

                    if (refractory_remaining != 0) begin
                        refractory_remaining <= refractory_remaining - 1'b1;
                    end

                    if (sample_index < BOOTSTRAP_LENGTH) begin
                        // 不丢样/压紧时间轴，前两秒只预热，不输出候选事件。
                        if (sample_index >= WINDOW_LENGTH) begin
                            bootstrap_sum <= bootstrap_sum + energy_next;
                            if (energy_next > bootstrap_peak) bootstrap_peak <= energy_next;
                        end
                        if (sample_index == BOOTSTRAP_LENGTH - 1) begin
                            bootstrap_latched_sum <= bootstrap_total;
                            bootstrap_latched_peak <= bootstrap_max;
                            bootstrap_phase <= 1;
                        end
                    end else if (bootstrap_ready && (previous_energy > energy_next)
                     && (previous_energy >= older_energy)
                     && (previous_energy >= threshold_next)
                     && (refractory_remaining == 0)) begin
                        // 局部能量峰满足阈值且不处于不应期时输出候选事件。
                        qrs_valid <= 1'b1;
                        qrs_sample_index <= corrected_sample_index;

                        if (have_last_qrs) begin
                            rr_interval_samples <= corrected_sample_index - last_qrs_index;
                        end

                        last_qrs_index <= corrected_sample_index;
                        have_last_qrs <= 1'b1;
                        refractory_remaining <= REFRACTORY_LENGTH - 1;
                        signal_level <= signal_level - (signal_level >> 3)
                                      + (previous_energy >> 3);
                    end else if (bootstrap_ready && (sample_index >= BOOTSTRAP_LENGTH) && (previous_energy > energy_next)
                              && (previous_energy >= older_energy) && (previous_energy < threshold_next)) begin
                        // 未超过阈值时，用当前能量缓慢更新噪声估计。
                        noise_level <= noise_level - (noise_level >> 3)
                                     + (previous_energy >> 3);
                    end
                end
            end
        end
    end

endmodule
