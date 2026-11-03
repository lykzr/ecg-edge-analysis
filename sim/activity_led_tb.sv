`timescale 1ns/1ps
module activity_led_tb;
    reg clk=0,resetn=0,active=0;
    wire led;
    always #5 clk=~clk;
    ecg_activity_led #(.HALF_PERIOD(3)) dut(clk,resetn,active,led);
    task tick;
        @(posedge clk); #1;
    endtask
    initial begin
        tick(); if(led!==0) $fatal(1,"复位未熄灭");
        @(negedge clk); resetn=1;
        repeat(4) begin tick(); if(led!==0) $fatal(1,"空闲未熄灭"); end
        @(negedge clk); active=1;
        tick(); if(led!==1) $fatal(1,"会话首周期未亮");
        repeat(2) begin tick(); if(led!==1) $fatal(1,"亮灯时长不足"); end
        tick(); if(led!==0) $fatal(1,"没有闪烁");
        repeat(3) tick(); if(led!==1) $fatal(1,"没有再次亮灯");
        @(negedge clk); active=0;
        tick(); if(led!==0) $fatal(1,"会话结束未熄灭");
        @(negedge clk); active=1;
        tick(); if(led!==1) $fatal(1,"再次开始未亮");
        @(negedge clk); resetn=0;
        tick(); if(led!==0) $fatal(1,"运行中复位未熄灭");
        $display("PASS ACTIVITY_LED"); $finish;
    end
endmodule
