// 冻结v92/fold0三路并行树遍历。输入IEEE754 float32，输出有符号Q40分数。
// softmax仍由ARM计算；本模块不负责检测、特征提取或信号质量判断。
`include "hgb_pl_config.vh"
module ecg_hgb_lane #(
    parameter NODE_FILE="nodes_0.mem", ROOT_FILE="roots_0.mem",
    parameter signed [63:0] BASELINE=0
)(
    input wire clk, resetn, start,
    output wire [7:0] feature_addr, input wire [31:0] feature_data,
    output reg done, output reg signed [63:0] score
);
    (* rom_style="block" *) reg [127:0] nodes[0:4095];
    reg [11:0] roots[0:63];
    initial begin $readmemh(NODE_FILE,nodes);$readmemh(ROOT_FILE,roots);end
    reg [127:0] node;
    reg [11:0] addr;
    reg [5:0] tree;
    reg [1:0] state;
    wire [31:0] clean_float=(feature_data[30:0]==0)?32'b0:feature_data;
    wire [31:0] ordered=clean_float[31]?~clean_float:(clean_float^32'h80000000);
    assign feature_addr=node[126:119];
    always @(posedge clk) begin
        if(!resetn) begin state<=0;done<=0;score<=0;addr<=0;tree<=0;node<=0;end
        else case(state)
            0: if(start) begin score<=BASELINE;tree<=0;addr<=roots[0];done<=0;state<=1;end
            1: begin node<=nodes[addr];state<=2;end
            2: if(node[127]) begin
                score<=score+$signed({node[62],node[62:0]});
                if(tree==63) begin done<=1;state<=0;end
                else begin tree<=tree+1'b1;addr<=roots[tree+1'b1];state<=1;end
            end else begin
                addr<=(ordered<=node[94:63])?node[118:107]:node[106:95];state<=1;
            end
            default: state<=0;
        endcase
    end
endmodule

module ecg_hgb_core(
    input wire clk,resetn,start,
    input wire feature_we,input wire [7:0] feature_index,input wire [31:0] feature_value,
    output reg busy,done,error,output reg [31:0] cycles,
    output wire signed [63:0] score0,score1,score2
);
    // 三份192x32特征存储避免三路树遍历争用；运行期间拒绝修改。
    reg [31:0] features[0:191];
    reg [191:0] present;
    wire [7:0] a0,a1,a2;
    wire d0,d1,d2;
    reg launch;
    wire finite_value=(feature_value[30:23]!=8'hff);
    ecg_hgb_lane #(.BASELINE(`HGB_BASE_0)) l0(clk,resetn,launch,a0,features[a0],d0,score0);
    ecg_hgb_lane #(.NODE_FILE("nodes_1.mem"),.ROOT_FILE("roots_1.mem"),.BASELINE(`HGB_BASE_1)) l1(clk,resetn,launch,a1,features[a1],d1,score1);
    ecg_hgb_lane #(.NODE_FILE("nodes_2.mem"),.ROOT_FILE("roots_2.mem"),.BASELINE(`HGB_BASE_2)) l2(clk,resetn,launch,a2,features[a2],d2,score2);
    always @(posedge clk) begin
        if(!resetn) begin busy<=0;done<=0;error<=0;cycles<=0;launch<=0;present<=0;end
        else begin
            launch<=0;
            if(feature_we && !busy) begin
                if(feature_index<192) begin
                    present[feature_index]<=finite_value;
                    if(finite_value)features[feature_index]<=feature_value;
                end
            end
            if(start && !busy) begin
                done<=0;error<=0;cycles<=0;
                if((&present) && !feature_we) begin busy<=1;launch<=1;end
                else begin error<=1;done<=1;end
            end
            if(busy) begin
                cycles<=cycles+1'b1;
                // 启动首拍不能采纳上次保留的done。
                if(!launch && cycles>1 && d0 && d1 && d2) begin busy<=0;done<=1;end
            end
        end
    end
endmodule
