`timescale 1ns/1ps
`include "vectors.vh"
module ecg_hgb_axi_tb;
reg  s_axi_aclk=0;
reg  s_axi_aresetn=0;
reg [16-1:0] s_axi_awaddr=0;
reg [2:0] s_axi_awprot=0;
reg  s_axi_awvalid=0;
wire  s_axi_awready;
reg [32-1:0] s_axi_wdata=0;
reg [(32/8)-1:0] s_axi_wstrb=0;
reg  s_axi_wvalid=0;
wire  s_axi_wready;
wire [1:0] s_axi_bresp;
wire  s_axi_bvalid;
reg  s_axi_bready=0;
reg [16-1:0] s_axi_araddr=0;
reg [2:0] s_axi_arprot=0;
reg  s_axi_arvalid=0;
wire  s_axi_arready;
wire [32-1:0] s_axi_rdata;
wire [1:0] s_axi_rresp;
wire  s_axi_rvalid;
reg  s_axi_rready=0;
always #5 s_axi_aclk=~s_axi_aclk;
ecg_hgb_axi_lite dut(.s_axi_aclk(s_axi_aclk),.s_axi_aresetn(s_axi_aresetn),.s_axi_awaddr(s_axi_awaddr),.s_axi_awprot(s_axi_awprot),.s_axi_awvalid(s_axi_awvalid),.s_axi_awready(s_axi_awready),.s_axi_wdata(s_axi_wdata),.s_axi_wstrb(s_axi_wstrb),.s_axi_wvalid(s_axi_wvalid),.s_axi_wready(s_axi_wready),.s_axi_bresp(s_axi_bresp),.s_axi_bvalid(s_axi_bvalid),.s_axi_bready(s_axi_bready),.s_axi_araddr(s_axi_araddr),.s_axi_arprot(s_axi_arprot),.s_axi_arvalid(s_axi_arvalid),.s_axi_arready(s_axi_arready),.s_axi_rdata(s_axi_rdata),.s_axi_rresp(s_axi_rresp),.s_axi_rvalid(s_axi_rvalid),.s_axi_rready(s_axi_rready));
reg [31:0] features[0:`HGB_TEST_COUNT*192-1];reg [63:0] expected[0:`HGB_TEST_COUNT*3-1];
reg [31:0] result,lo,hi;integer v,i,k,n;
task write_reg(input [15:0] addr,input [31:0] data,input integer gap,input [3:0] strobe,input [1:0] response);
begin
 @(negedge s_axi_aclk);s_axi_awaddr=addr;s_axi_awvalid=1;
 while(!s_axi_awready)@(negedge s_axi_aclk);
 @(negedge s_axi_aclk);s_axi_awvalid=0;
 repeat(gap)@(negedge s_axi_aclk);
 s_axi_wdata=data;s_axi_wstrb=strobe;s_axi_wvalid=1;
 while(!s_axi_wready)@(negedge s_axi_aclk);
 @(negedge s_axi_aclk);s_axi_wvalid=0;
 while(!s_axi_bvalid)@(negedge s_axi_aclk);
 if(s_axi_bresp!==response)$fatal(1,"AXI write response addr=%h",addr);
 repeat(3)@(negedge s_axi_aclk);
 if(!s_axi_bvalid)$fatal(1,"AXI response lost under backpressure");
 s_axi_bready=1;@(negedge s_axi_aclk);s_axi_bready=0;
end endtask
task read_reg(input [15:0] addr,input [1:0] response);
begin
 @(negedge s_axi_aclk);s_axi_araddr=addr;s_axi_arvalid=1;
 while(!s_axi_arready)@(negedge s_axi_aclk);
 @(negedge s_axi_aclk);s_axi_arvalid=0;
 while(!s_axi_rvalid)@(negedge s_axi_aclk);
 result=s_axi_rdata;repeat(3)@(negedge s_axi_aclk);
 if(!s_axi_rvalid || s_axi_rdata!==result || s_axi_rresp!==response)$fatal(1,"AXI read hold");
 s_axi_rready=1;@(negedge s_axi_aclk);s_axi_rready=0;
end endtask
initial begin
 $readmemh("features.mem",features);$readmemh("scores.mem",expected);
 repeat(4)@(negedge s_axi_aclk);s_axi_aresetn=1;
 read_reg(0,0);if(result!==32'h48474231)$fatal(1,"ID");
 write_reg(16'h100,0,2,1,2);read_reg(16'h30,2);
 write_reg(4,1,0,15,0);read_reg(4,0);if(result!==6)$fatal(1,"missing input");
 for(v=0;v<3;v=v+1)begin
  for(i=0;i<192;i=i+1)write_reg(16'h100+i*4,features[v*192+i],i%3,15,0);
  write_reg(4,1,0,15,0);write_reg(16'h100,0,0,15,2);
  n=0;result=0;
  while(!(result&2) && n<1000)begin read_reg(4,0);n=n+1;end
  if(n==1000 || result&4)$fatal(1,"completion");
  for(k=0;k<3;k=k+1)begin
   read_reg(16'h10+k*8,0);lo=result;read_reg(16'h14+k*8,0);hi=result;
   if({hi,lo}!==expected[v*3+k])$fatal(1,"AXI score vector=%d class=%d",v,k);
  end
  read_reg(8,0);if(result==0 || result>1000)$fatal(1,"cycle count");
  $display("AXI vector=%d core_cycles=%d",v,result);
 end
 $display("PASS HGB AXI separated AW/W, backpressure, errors, scores");$finish;
end
initial begin #5000000;$fatal(1,"timeout");end
endmodule
