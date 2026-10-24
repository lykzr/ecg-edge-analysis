// INT8准备算子：配置必须由主机证明INT32最坏累加不溢出。
// 向量接口用于算子仿真/综合，不是最终AXI或CNN加速器接口。
module ecg_int8_conv #(
 parameter integer CIN=1, COUT=1, LENGTH=8, KERNEL=3,
 parameter integer SHIFT=0, RELU=0
)(input logic clk, reset, start,
 input logic signed [7:0] x [0:CIN*LENGTH-1],
 input logic signed [7:0] w [0:COUT*CIN*KERNEL-1],
 input logic signed [31:0] bias [0:COUT-1],
 output logic busy, done,
 output logic signed [7:0] y [0:COUT*(LENGTH-KERNEL+1)-1]);
 localparam integer OUTLEN=LENGTH-KERNEL+1;
 integer oc,pos,ic,k;
 logic signed [31:0] accum;
 logic signed [15:0] product;
 logic signed [31:0] nextacc;
 function automatic signed [7:0] quant(input logic signed [31:0] a);
  logic signed [63:0] mag, rounded;
  begin
   mag=a; if(mag<0) mag=-mag;
   if(SHIFT>0) mag=(mag+(64'sd1 << (SHIFT-1))) >>> SHIFT;
   rounded=a<0 ? -mag : mag;
   if(RELU && rounded<0) quant=0;
   else if(rounded>127) quant=127;
   else if(rounded < -128) quant=-128;
   else quant=rounded[7:0];
  end
 endfunction
 always_comb begin
  product=$signed(x[ic*LENGTH+pos+k])*$signed(w[(oc*CIN+ic)*KERNEL+k]);
  nextacc=accum+{{16{product[15]}},product};
 end
 always_ff @(posedge clk) begin
  if(reset) begin busy<=0;done<=0;oc<=0;pos<=0;ic<=0;k<=0;accum<=0; end
  else begin
   done<=0;
   if(!busy) begin
    if(start) begin busy<=1;oc<=0;pos<=0;ic<=0;k<=0;accum<=bias[0];end
   end else if(k==KERNEL-1 && ic==CIN-1) begin
    y[oc*OUTLEN+pos]<=quant(nextacc);ic<=0;k<=0;
    if(pos==OUTLEN-1) begin
     pos<=0;
     if(oc==COUT-1) begin busy<=0;done<=1;end
     else begin oc<=oc+1;accum<=bias[oc+1];end
    end else begin pos<=pos+1;accum<=bias[oc];end
   end else begin
    accum<=nextacc;
    if(k==KERNEL-1) begin k<=0;ic<=ic+1;end else k<=k+1;
   end
  end
 end
endmodule

module ecg_int8_maxpool #(parameter integer LENGTH=8, WIDTH=2)(
 input logic signed [7:0] x [0:LENGTH-1],
 output logic signed [7:0] y [0:LENGTH/WIDTH-1]);
 integer i,j;
 always_comb begin
  for(i=0;i<LENGTH/WIDTH;i=i+1) begin
   y[i]=x[i*WIDTH];
   for(j=1;j<WIDTH;j=j+1) if($signed(x[i*WIDTH+j])>$signed(y[i])) y[i]=x[i*WIDTH+j];
  end
 end
endmodule
