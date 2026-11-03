// 工作会话指示：会话有效时2Hz闪烁，空闲/复位时熄灭；不代表逐周期CNN busy。
module ecg_activity_led #(
    parameter integer HALF_PERIOD = 25000000
)(
    input wire clk,
    input wire resetn,
    input wire active,
    output reg work_led = 1'b0
);
    localparam integer WIDTH = HALF_PERIOD > 1 ? $clog2(HALF_PERIOD) : 1;
    reg [WIDTH-1:0] count = 0;
    reg was_active = 0;
    always @(posedge clk) begin
        if (!resetn || !active) begin
            count <= 0;
            work_led <= 0;
            was_active <= 0;
        end else begin
            was_active <= 1;
            if (!was_active) begin
                count <= 0;
                work_led <= 1;
            end else if (count == HALF_PERIOD-1) begin
                count <= 0;
                work_led <= ~work_led;
            end else count <= count + 1'b1;
        end
    end
endmodule
