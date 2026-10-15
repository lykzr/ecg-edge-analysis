// 心电 QRS 候选检测模块（算法起步版本）。
// 使用一阶差分绝对值、滑动积分、自适应阈值和不应期。
// 本模块不替代临床设备；参数需要根据实际采样率、幅值和参考标注校准。
module ecg_qrs_detector #(
    // 输入采样位宽、采样率、积分窗口和不应期时长。
    parameter integer SAMPLE_WIDTH = 16,
    parameter integer SAMPLE_RATE_HZ = 360,
    parameter integer INTEGRATION_MS = 120,
    parameter integer REFRACTORY_MS = 200,
    // 积分能量位宽，以及自适应阈值的初始噪声/信号估计值。
    parameter integer ENERGY_WIDTH = 24,
    parameter integer INITIAL_NOISE_LEVEL = 4096,
    parameter integer INITIAL_SIGNAL_LEVEL = 16384
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

    logic signed [SAMPLE_WIDTH:0] derivative;
    logic [SAMPLE_WIDTH:0]        absolute_derivative;
    logic [ENERGY_WIDTH-1:0]      derivative_term;
    logic [ENERGY_WIDTH-1:0]      energy_next;
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

                    if (write_pointer == WINDOW_LENGTH - 1) begin
                        write_pointer <= '0;
                    end else begin
                        write_pointer <= write_pointer + 1'b1;
                    end

                    if (refractory_remaining != 0) begin
                        refractory_remaining <= refractory_remaining - 1'b1;
                    end

                    if ((previous_energy < threshold_next)
                     && (energy_next >= threshold_next)
                     && (refractory_remaining == 0)) begin
                        // 阈值上穿且不处于不应期时，输出一个 QRS 候选事件。
                        qrs_valid <= 1'b1;
                        qrs_sample_index <= corrected_sample_index;

                        if (have_last_qrs) begin
                            rr_interval_samples <= corrected_sample_index - last_qrs_index;
                        end

                        last_qrs_index <= corrected_sample_index;
                        have_last_qrs <= 1'b1;
                        refractory_remaining <= REFRACTORY_LENGTH - 1;
                        signal_level <= signal_level - (signal_level >> 3)
                                      + (energy_next >> 3);
                    end else if (energy_next < threshold_next) begin
                        // 未超过阈值时，用当前能量缓慢更新噪声估计。
                        noise_level <= noise_level - (noise_level >> 3)
                                     + (energy_next >> 3);
                    end
                end
            end
        end
    end

endmodule
