`timescale 1ns/1ps
module tb_axi_lite;
 reg clk=0; always #5 clk=~clk;
 reg resetn=0;
 reg [15:0] awaddr=0,araddr=0;
 reg [31:0] wdata=0;
 reg [3:0] wstrb=0;
 reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
 wire awready,wready,bvalid,arready,rvalid;
 wire [1:0] bresp,rresp;
 wire [31:0] rdata;
 integer accepted_samples=0;
 ecg_qrs_axi_lite #(.EVENT_FIFO_DEPTH(2), .SAMPLE_RATE_HZ(500)) dut(.s_axi_aclk(clk),.s_axi_aresetn(resetn),
 .s_axi_awaddr(awaddr),.s_axi_awprot(3'b0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
 .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
 .s_axi_araddr(araddr),.s_axi_arprot(3'b0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
 .s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready));
 always @(posedge clk) if(resetn && dut.sample_valid) accepted_samples<=accepted_samples+1;
 task address(input [15:0] value);
 begin @(negedge clk); awaddr=value; awvalid=1; @(posedge clk); while(!awready) @(posedge clk); @(negedge clk); awvalid=0; end
 endtask
 task data(input [31:0] value,input [3:0] mask);
 begin @(negedge clk); wdata=value; wstrb=mask; wvalid=1; @(posedge clk); while(!wready) @(posedge clk); @(negedge clk); wvalid=0; end
 endtask
 task response(input [1:0] expected=2'b00);
 begin
  wait(bvalid); if(bresp!==expected)$fatal(1,"Unexpected write response");
  repeat(3) begin @(posedge clk); if(!bvalid)$fatal(1,"BVALID dropped under backpressure"); end
  @(negedge clk); bready=1; @(posedge clk); @(negedge clk); bready=0;
  repeat(3) @(posedge clk);
 end endtask
 task write_sample(input signed [15:0] value);
 begin fork address(16'h0000);data({16'b0,value},4'b0011);join response();end endtask
 task read_reg(input [15:0] addr,output [31:0] value);
 reg [31:0] held;
 begin
  @(negedge clk);araddr=addr;arvalid=1;
  @(posedge clk);while(!arready)@(posedge clk);
  @(negedge clk);arvalid=0;wait(rvalid);held=rdata;
  repeat(3)begin @(posedge clk);if(!rvalid || rdata!==held)$fatal(1,"Read response changed while stalled");end
  value=held;@(negedge clk);rready=1;@(posedge clk);@(negedge clk);rready=0;
 end endtask
 reg [31:0] status,index1,index2,value;
 integer i;
 initial begin
  repeat(4)@(posedge clk);@(negedge clk);resetn=1;
  address(0);repeat(4)@(posedge clk);data(0,4'b0011);response();
  data(0,4'b0011);repeat(4)@(posedge clk);address(0);response();
  if(accepted_samples!=2)$fatal(1,"Split channels produced wrong sample count");
  fork address(0);data(32'hffff,4'b0000);join response();
  if(accepted_samples!=2)$fatal(1,"Zero strobe submitted a sample");
  write_sample(16'sd20000);read_reg(4,status);read_reg(8,index1);
  if(!status[0])$fatal(1,"Synthetic edge did not produce an event");
  for(i=0;i<100;i=i+1)write_sample(0);
  write_sample(16'sd20000);read_reg(4,status);read_reg(8,index2);
  if(!status[0] || index2!==index1)$fatal(1,"Unconsumed FIFO head was overwritten");
  read_reg('h1c,value);if(value!=2)$fatal(1,"Two events were not queued");
  read_reg('h24,value);if(value!=500)$fatal(1,"Sample rate parameter not exposed");
  // 队列已满：新事件不能覆盖旧事件，且必须记录溢出。
  @(negedge clk);force dut.qrs_valid=1;force dut.qrs_sample_index=1001;force dut.rr_interval_samples=111;
  @(posedge clk);@(negedge clk);force dut.qrs_valid=0;
  read_reg(4,status);if(status[1:0]!=3)$fatal(1,"Overflow not reported");
  read_reg('h20,value);if(value!=1)$fatal(1,"Dropped event count incorrect");
  read_reg(8,index2);if(index2!=index1)$fatal(1,"Overflow replaced queued event");
  // 满队列同周期出队与入队：保持两个事件，不能额外丢弃。
  fork
   begin address(4);data(1,1);response();end
   begin
    wait(dut.write_commit);@(negedge clk);
    force dut.qrs_valid=1;force dut.qrs_sample_index=1002;force dut.rr_interval_samples=222;
    @(posedge clk);@(negedge clk);force dut.qrs_valid=0;
   end
  join
  read_reg('h1c,value);if(value!=2)$fatal(1,"Simultaneous push/pop changed occupancy");
  read_reg('h20,value);if(value!=1)$fatal(1,"Simultaneous push/pop dropped event");
  read_reg(8,index2);if(index2==index1)$fatal(1,"Pop did not advance head");
  address(4);data(1,1);response();
  read_reg(8,value);if(value!=1002)$fatal(1,"New event not preserved after full push/pop");
  read_reg('hc,value);if(value!=222)$fatal(1,"Event fields are not coherent");
  read_reg('h18,value);if(value!=4)$fatal(1,"Event sequence incorrect");
  address(4);data(3,1);response();
  read_reg(4,status);if(status!=0)$fatal(1,"Empty queue/overflow clear failed");
  read_reg('h20,value);if(value!=1)$fatal(1,"Overflow clear erased cumulative count");
  i=accepted_samples;
  fork address('h40);data('h1234,3);join response(2'b10);
  if(accepted_samples!=i)$fatal(1,"Address 0x40 still aliases sample register");
  fork address('h01);data('h1234,3);join response(2'b10);
  if(accepted_samples!=i)$fatal(1,"Unaligned write submitted a sample");
  read_reg('h40,value);if(rresp!=2'b10)$fatal(1,"Invalid read did not return SLVERR");
  $display("PASS AXI split channels/backpressure, FIFO snapshots/overflow/full push-pop, address validation, sample rate parameter");
  $finish;
 end
 initial begin #200000;$fatal(1,"Timeout");end
endmodule
