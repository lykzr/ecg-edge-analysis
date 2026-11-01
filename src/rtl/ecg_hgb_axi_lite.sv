// HGB分类AXI-Lite外设；寄存器定义见docs/download_guide.md的HGB PL段。
module ecg_hgb_axi_lite #(
    parameter integer C_S_AXI_ADDR_WIDTH=16,
    parameter integer C_S_AXI_DATA_WIDTH=32
)(
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
    reg [15:0] aw;
    reg [31:0] wd;
    reg [3:0] ws;
    reg aw_full,w_full;
    reg start,we;
    reg [7:0] feature_index;
    reg [31:0] feature_value;
    wire busy,done,error;
    wire [31:0] cycles;
    wire signed [63:0] s0,s1,s2;
    wire commit=aw_full && w_full && !s_axi_bvalid;
    assign s_axi_awready=s_axi_aresetn && !aw_full && !s_axi_bvalid;
    assign s_axi_wready=s_axi_aresetn && !w_full && !s_axi_bvalid;
    assign s_axi_arready=s_axi_aresetn && !s_axi_rvalid;
    ecg_hgb_core core(s_axi_aclk,s_axi_aresetn,start,we,feature_index,feature_value,busy,done,error,cycles,s0,s1,s2);
    always @(posedge s_axi_aclk) begin
        if(!s_axi_aresetn) begin
            aw_full<=0;w_full<=0;s_axi_bvalid<=0;s_axi_bresp<=0;
            s_axi_rvalid<=0;s_axi_rresp<=0;s_axi_rdata<=0;start<=0;we<=0;
            aw<=0;wd<=0;ws<=0;feature_index<=0;feature_value<=0;
        end else begin
            start<=0;we<=0;
            if(s_axi_awvalid && s_axi_awready) begin aw<=s_axi_awaddr;aw_full<=1;end
            if(s_axi_wvalid && s_axi_wready) begin wd<=s_axi_wdata;ws<=s_axi_wstrb;w_full<=1;end
            if(s_axi_bvalid && s_axi_bready)s_axi_bvalid<=0;
            if(commit) begin
                aw_full<=0;w_full<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
                if(busy) s_axi_bresp<=2;
                else if(aw==16'h0004 && ws==4'hf && wd==1) start<=1;
                else if(aw>=16'h0100 && aw<16'h0400 && aw[1:0]==0 && ws==4'hf) begin
                    feature_index<=(aw-16'h0100)>>2;feature_value<=wd;we<=1;
                end else s_axi_bresp<=2;
            end
            if(s_axi_rvalid && s_axi_rready)s_axi_rvalid<=0;
            if(s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid<=1;s_axi_rresp<=0;
                case(s_axi_araddr)
                    16'h00:s_axi_rdata<=32'h48474231;
                    16'h04:s_axi_rdata<={29'b0,error,done,busy};
                    16'h08:s_axi_rdata<=cycles;
                    16'h0c:s_axi_rdata<=32'd100000000;
                    16'h10:s_axi_rdata<=s0[31:0];16'h14:s_axi_rdata<=s0[63:32];
                    16'h18:s_axi_rdata<=s1[31:0];16'h1c:s_axi_rdata<=s1[63:32];
                    16'h20:s_axi_rdata<=s2[31:0];16'h24:s_axi_rdata<=s2[63:32];
                    16'h28:s_axi_rdata<=32'd40;
                    default:begin s_axi_rdata<=0;s_axi_rresp<=2;end
                endcase
            end
        end
    end
endmodule
