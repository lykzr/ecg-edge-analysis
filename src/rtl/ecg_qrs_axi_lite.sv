// AXI4-Lite 控制接口：PS 写入心电采样，读取 QRS 检测结果。
// 寄存器偏移：0x00 写采样；0x04 状态；0x08 QRS 位置；0x0C RR 间期；
// 结果按事件 FIFO 保存，软件读取队首后写 0x04 bit0 弹出一个事件。
// 溢出时保留已有事件，记录被丢弃的新事件，详见 docs/register_map.md。
module ecg_qrs_axi_lite #(
    parameter integer C_S_AXI_ADDR_WIDTH = 16,
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer SAMPLE_RATE_HZ = 360,
    parameter integer INTEGRATION_MS = 120,
    parameter integer REFRACTORY_MS = 200,
    parameter integer EVENT_FIFO_DEPTH = 8
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input  wire                              s_axi_aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
    input  wire                              s_axi_aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXI, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 16, FREQ_HZ 100000000" *)
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     s_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *)
    input  wire [2:0]                        s_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *)
    input  wire                              s_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *)
    output wire                              s_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WDATA" *)
    input  wire [C_S_AXI_DATA_WIDTH-1:0]      s_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *)
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] s_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WVALID" *)
    input  wire                              s_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI WREADY" *)
    output wire                              s_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BRESP" *)
    output reg  [1:0]                        s_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BVALID" *)
    output reg                               s_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI BREADY" *)
    input  wire                              s_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *)
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]     s_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *)
    input  wire [2:0]                        s_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *)
    input  wire                              s_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *)
    output wire                              s_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RDATA" *)
    output reg  [C_S_AXI_DATA_WIDTH-1:0]      s_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RRESP" *)
    output reg  [1:0]                        s_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RVALID" *)
    output reg                               s_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXI RREADY" *)
    input  wire                              s_axi_rready
);

    // AXI 地址/数据通道分开缓存，兼容 AW 与 W 不同周期到达。
    reg [C_S_AXI_ADDR_WIDTH-1:0] write_address;
    reg [C_S_AXI_DATA_WIDTH-1:0] write_data;
    reg [(C_S_AXI_DATA_WIDTH/8)-1:0] write_strobe;
    reg write_address_full;
    reg write_data_full;
    reg [31:0] read_value;
    reg read_address_valid;

    reg sample_valid;
    reg signed [15:0] sample_in;
    localparam integer EVENT_POINTER_WIDTH = (EVENT_FIFO_DEPTH <= 1) ? 1 : $clog2(EVENT_FIFO_DEPTH);
    localparam integer EVENT_COUNT_WIDTH = $clog2(EVENT_FIFO_DEPTH + 1);
    reg [31:0] event_index [0:EVENT_FIFO_DEPTH-1];
    reg [31:0] event_rr [0:EVENT_FIFO_DEPTH-1];
    reg [31:0] event_sequence [0:EVENT_FIFO_DEPTH-1];
    reg [EVENT_POINTER_WIDTH-1:0] event_read_pointer, event_write_pointer;
    reg [EVENT_COUNT_WIDTH-1:0] event_count;
    reg [31:0] total_events, dropped_events;
    reg event_overflow;
    wire qrs_pending = (event_count != 0);
    wire qrs_valid;
    wire [31:0] qrs_sample_index;
    wire [31:0] rr_interval_samples;
    wire [23:0] integrated_energy;
    wire [23:0] adaptive_threshold;

    wire write_address_handshake = s_axi_awvalid && s_axi_awready;
    wire write_data_handshake = s_axi_wvalid && s_axi_wready;
    wire write_commit = write_address_full && write_data_full;
    wire event_pop = write_commit && (write_address == 'h04)
                   && write_strobe[0] && write_data[0] && qrs_pending;
    wire event_push = qrs_valid && ((event_count < EVENT_FIFO_DEPTH) || event_pop);

    assign s_axi_awready = s_axi_aresetn && !write_address_full && !s_axi_bvalid;
    assign s_axi_wready  = s_axi_aresetn && !write_data_full && !s_axi_bvalid;
    assign s_axi_arready = s_axi_aresetn && !s_axi_rvalid;

    // 解码完整相对地址；未实现或未对齐地址返回 SLVERR，不产生镜像。
    always @* begin
        read_address_valid = 1'b1;
        case (s_axi_araddr)
            'h00: read_value = 32'b0;
            'h04: read_value = {30'b0, event_overflow, qrs_pending};
            'h08: read_value = qrs_pending ? event_index[event_read_pointer] : 32'b0;
            'h0c: read_value = qrs_pending ? event_rr[event_read_pointer] : 32'b0;
            'h10: read_value = {8'b0, integrated_energy};
            'h14: read_value = {8'b0, adaptive_threshold};
            'h18: read_value = qrs_pending ? event_sequence[event_read_pointer] : 32'b0;
            'h1c: read_value = event_count;
            'h20: read_value = dropped_events;
            'h24: read_value = SAMPLE_RATE_HZ;
            'h28: read_value = INTEGRATION_MS;
            'h2c: read_value = REFRACTORY_MS;
            'h30: read_value = total_events;
            default: begin read_value = 32'b0; read_address_valid = 1'b0; end
        endcase
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            write_address      <= '0;
            write_data         <= '0;
            write_strobe       <= '0;
            write_address_full <= 1'b0;
            write_data_full    <= 1'b0;
            s_axi_bresp        <= 2'b00;
            s_axi_bvalid       <= 1'b0;
            s_axi_rdata        <= '0;
            s_axi_rresp        <= 2'b00;
            s_axi_rvalid       <= 1'b0;
            sample_valid       <= 1'b0;
            sample_in          <= '0;
            event_read_pointer <= '0;
            event_write_pointer <= '0;
            event_count <= '0;
            total_events <= '0;
            dropped_events <= '0;
            event_overflow <= 1'b0;
        end else begin
            sample_valid <= 1'b0;

            if (write_address_handshake) begin
                write_address <= s_axi_awaddr;
                write_address_full <= 1'b1;
            end
            if (write_data_handshake) begin
                write_data <= s_axi_wdata;
                write_strobe <= s_axi_wstrb;
                write_data_full <= 1'b1;
            end

            if (write_commit) begin
                write_address_full <= 1'b0;
                write_data_full <= 1'b0;
                s_axi_bresp <= 2'b00;
                s_axi_bvalid <= 1'b1;
                case (write_address)
                    'h00: begin
                        // 0x00：低两个字节组成一个有符号 16 位采样。
                        if (write_strobe[1:0] == 2'b11) begin
                            sample_in <= write_data[15:0];
                            sample_valid <= 1'b1;
                        end
                    end
                    'h04: begin
                        // bit0 消费队首；bit1 清除溢出提示，累计丢弃数保留。
                        if (write_strobe[0] && write_data[1])
                            event_overflow <= 1'b0;
                    end
                    default: s_axi_bresp <= 2'b10;
                endcase
            end

            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 1'b0;

            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rdata <= read_value;
                s_axi_rresp <= read_address_valid ? 2'b00 : 2'b10;
                s_axi_rvalid <= 1'b1;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end

            if (event_pop)
                event_read_pointer <= (event_read_pointer == EVENT_FIFO_DEPTH-1)
                                    ? '0 : event_read_pointer + 1'b1;
            if (qrs_valid) begin
                total_events <= total_events + 1'b1;
                if (event_push) begin
                    event_index[event_write_pointer] <= qrs_sample_index;
                    event_rr[event_write_pointer] <= rr_interval_samples;
                    event_sequence[event_write_pointer] <= total_events + 1'b1;
                    event_write_pointer <= (event_write_pointer == EVENT_FIFO_DEPTH-1)
                                         ? '0 : event_write_pointer + 1'b1;
                end else begin
                    event_overflow <= 1'b1;
                    dropped_events <= dropped_events + 1'b1;
                end
            end
            case ({event_push, event_pop})
                2'b10: event_count <= event_count + 1'b1;
                2'b01: event_count <= event_count - 1'b1;
                default: begin end
            endcase
        end
    end

    ecg_qrs_detector #(
        .SAMPLE_RATE_HZ(SAMPLE_RATE_HZ),
        .INTEGRATION_MS(INTEGRATION_MS),
        .REFRACTORY_MS(REFRACTORY_MS)
    ) detector (
        .clk                  (s_axi_aclk),
        .rst_n                (s_axi_aresetn),
        .sample_valid         (sample_valid),
        .sample_in            (sample_in),
        .qrs_valid            (qrs_valid),
        .qrs_sample_index     (qrs_sample_index),
        .rr_interval_samples  (rr_interval_samples),
        .integrated_energy    (integrated_energy),
        .adaptive_threshold   (adaptive_threshold)
    );

endmodule
