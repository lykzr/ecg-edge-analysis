`timescale 1ns/1ps
// 真实 AXI 写样本驱动默认检测器，不 force 事件；对应 PS 自检的合成输入。
module tb_ecg_smoke #(parameter integer RATE=360);
    localparam integer FIRST_POS=100-(RATE*120/1000)/2;
    reg clk=0; always #5 clk=~clk;
    reg resetn=0;
    reg [15:0] awaddr=0, araddr=0;
    reg [31:0] wdata=0;
    reg awvalid=0, wvalid=0, bready=0, arvalid=0, rready=0;
    wire awready, wready, bvalid, arready, rvalid;
    wire [1:0] bresp, rresp;
    wire [31:0] rdata;
    ecg_qrs_axi_lite #(.SAMPLE_RATE_HZ(RATE)) dut(
        .s_axi_aclk(clk), .s_axi_aresetn(resetn),
        .s_axi_awaddr(awaddr), .s_axi_awprot(3'b0),
        .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(4'hf),
        .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(3'b0),
        .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp),
        .s_axi_rvalid(rvalid), .s_axi_rready(rready));

    task write_reg(input [15:0] addr, input [31:0] data);
        begin
            @(negedge clk); awaddr=addr; wdata=data; awvalid=1; wvalid=1;
            fork
                begin @(posedge clk); while(!awready) @(posedge clk);
                    @(negedge clk); awvalid=0; end
                begin @(posedge clk); while(!wready) @(posedge clk);
                    @(negedge clk); wvalid=0; end
            join
            wait(bvalid); if(bresp!==0) $fatal(1,"Write response failed");
            @(negedge clk); bready=1;
            @(posedge clk); @(negedge clk); bready=0;
            repeat(3) @(posedge clk);
        end
    endtask

    task check_reg(input [15:0] addr, input [31:0] expected);
        reg [31:0] actual;
        begin
            @(negedge clk); araddr=addr; arvalid=1;
            @(posedge clk); while(!arready) @(posedge clk);
            @(negedge clk); arvalid=0;
            wait(rvalid); actual=rdata;
            if(rresp!==0 || actual!==expected)
                $fatal(1,"Register %h got %0d expected %0d",addr,actual,expected);
            @(negedge clk); rready=1;
            @(posedge clk); @(negedge clk); rready=0;
        end
    endtask

    task head(input [31:0] index, input [31:0] rr, input [31:0] seq);
        begin check_reg('h08,index); check_reg('h0c,rr); check_reg('h18,seq); end
    endtask

    task zeros(input integer count);
        integer j;
        begin for(j=0;j<count;j=j+1) write_reg(0,0); end
    endtask

    task pulse_period(input integer ordinal);
        begin
            write_reg(0,(ordinal%2) ? 32'h0000b1e0 : 32'd20000);
            check_reg('h10,20000);
            zeros(RATE-1); check_reg('h10,0);
        end
    endtask

    integer i;
    initial begin
        repeat(4) @(posedge clk); @(negedge clk); resetn=1;
        check_reg('h24,RATE); check_reg('h28,120); check_reg('h2c,200);
        check_reg('h04,0); check_reg('h1c,0); check_reg('h20,0);
        check_reg('h30,0); check_reg('h10,0); check_reg('h14,7168);
        zeros(100); check_reg('h30,0); check_reg('h10,0);
        for(i=0;i<4;i=i+1) begin
            pulse_period(i);
            check_reg('h04,1); check_reg('h1c,1);
            check_reg('h30,i+1); check_reg('h20,0);
            head(FIRST_POS+RATE*i,i==0 ? 0 : RATE,i+1);
            write_reg(4,1); check_reg('h1c,0);
        end
        for(i=0;i<12;i=i+1) begin
            pulse_period(i);
            check_reg('h1c,i<8 ? i+1 : 8);
            check_reg('h30,i+5); check_reg('h20,i<8 ? 0 : i-7);
            check_reg('h04,i<8 ? 1 : 3);
            head(FIRST_POS+RATE*4,RATE,5);
        end
        write_reg(4,2); check_reg('h04,1); check_reg('h1c,8); check_reg('h20,4);
        for(i=0;i<8;i=i+1) begin
            head(FIRST_POS+RATE*(4+i),RATE,5+i);
            write_reg(4,1); check_reg('h1c,7-i);
        end
        check_reg('h04,0); head(0,0,0); check_reg('h30,16); check_reg('h20,4);
        $display("PASS ECG_SMOKE real samples, signed energy, indices/RR/sequence, FIFO retain/drop/pop/clear rate=%0d",RATE);
        $finish;
    end
    initial begin #2000000; $fatal(1,"ECG smoke timeout"); end
endmodule

// 独立顶层避免Windows批处理将参数赋值中的等号拆开。
module tb_ecg_smoke_500;
    tb_ecg_smoke #(.RATE(500)) test();
endmodule
