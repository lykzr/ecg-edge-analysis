`timescale 1ns/1ps
`include "vectors.vh"
module ecg_hgb_core_tb;
    reg clk=0;always #5 clk=~clk;
    reg resetn=0,start=0,we=0;reg [7:0] index=0;reg [31:0] value=0;
    wire busy,done,error;wire [31:0] cycles;wire signed [63:0] s0,s1,s2;
    reg [31:0] inputs[0:`HGB_TEST_COUNT*192-1];
    reg [63:0] scores[0:`HGB_TEST_COUNT*3-1];
    integer v,i,waited;
    ecg_hgb_core dut(clk,resetn,start,we,index,value,busy,done,error,cycles,s0,s1,s2);
    task write_feature(input integer n,input [31:0] data);
        @(negedge clk);we=1;index=n;value=data;
        @(negedge clk);we=0;
    endtask
    task go;
        @(negedge clk);start=1;
        @(negedge clk);start=0;waited=0;
        while(!done && waited<2000) begin @(negedge clk);waited=waited+1;end
        if(!done)$fatal(1,"分类超时");
    endtask
    initial begin
        $readmemh("features.mem",inputs);$readmemh("scores.mem",scores);
        repeat(4)@(negedge clk);resetn=1;
        go();if(!error)$fatal(1,"缺失输入未拒绝");
        for(v=0;v<`HGB_TEST_COUNT;v=v+1) begin
            for(i=0;i<192;i=i+1)write_feature(i,inputs[v*192+i]);
            go();
            if(error || s0!==scores[v*3] || s1!==scores[v*3+1] || s2!==scores[v*3+2])
                $fatal(1,"Q40分数不一致 vector=%0d got=%h,%h,%h expected=%h,%h,%h",v,s0,s1,s2,scores[v*3],scores[v*3+1],scores[v*3+2]);
        end
        write_feature(0,32'h7fc00000);go();if(!error)$fatal(1,"NaN未拒绝");
        write_feature(0,32'h7f800000);go();if(!error)$fatal(1,"Inf未拒绝");
        write_feature(0,0);go();if(error)$fatal(1,"合法输入未恢复");
        @(negedge clk);resetn=0;@(negedge clk);resetn=1;
        go();if(!error)$fatal(1,"复位未清除输入有效位");
        $display("PASS HGB PL core vectors=%0d cycles=%0d (simulation only)",`HGB_TEST_COUNT,cycles);$finish;
    end
    initial begin #20000000;$fatal(1,"全局超时");end
endmodule
