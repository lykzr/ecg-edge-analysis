// AXI4-Lite 控制接口：PS 写入心电采样，读取 QRS 检测结果。
// 寄存器偏移：0x00 写采样；0x04 状态；0x08 QRS 位置；0x0C RR 间期；
// 0x10 积分能量；0x14 自适应阈值。所有结果均为采样点或算法内部单位。
module ecg_qrs_axi_lite #(
    parameter integer C_S_AXI_ADDR_WIDTH = 16,
    parameter integer C_S_AXI_DATA_WIDTH = 32
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

    reg sample_valid;
    reg signed [15:0] sample_in;
    reg qrs_pending;
    wire qrs_valid;
    wire [31:0] qrs_sample_index;
    wire [31:0] rr_interval_samples;
    wire [23:0] integrated_energy;
    wire [23:0] adaptive_threshold;

    wire write_address_handshake = s_axi_awvalid && s_axi_awready;
    wire write_data_handshake = s_axi_wvalid && s_axi_wready;
    wire write_commit = write_address_full && write_data_full;

    assign s_axi_awready = s_axi_aresetn && !write_address_full && !s_axi_bvalid;
    assign s_axi_wready  = s_axi_aresetn && !write_data_full && !s_axi_bvalid;
    assign s_axi_arready = s_axi_aresetn && !s_axi_rvalid;

    // 地址低 6 位足以覆盖当前 0x00 至 0x14 的寄存器组。
    always @* begin
        case (s_axi_araddr[5:2])
            4'h1: read_value = {31'b0, qrs_pending};
            4'h2: read_value = qrs_sample_index;
            4'h3: read_value = rr_interval_samples;
            4'h4: read_value = {8'b0, integrated_energy};
            4'h5: read_value = {8'b0, adaptive_threshold};
            default: read_value = 32'b0;
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
            qrs_pending        <= 1'b0;
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
                case (write_address[5:2])
                    4'h0: begin
                        // 0x00：低两个字节组成一个有符号 16 位采样。
                        if (write_strobe[1:0] == 2'b11) begin
                            sample_in <= write_data[15:0];
                            sample_valid <= 1'b1;
                        end
                    end
                    4'h1: begin
                        // 0x04：写 bit0 清除待处理事件；新事件具有更高优先级。
                        if (write_strobe[0] && write_data[0])
                            qrs_pending <= 1'b0;
                    end
                    default: begin end
                endcase
            end

            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 1'b0;

            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rdata <= read_value;
                s_axi_rresp <= 2'b00;
                s_axi_rvalid <= 1'b1;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end

            if (qrs_valid)
                qrs_pending <= 1'b1;
        end
    end

    ecg_qrs_detector detector (
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
