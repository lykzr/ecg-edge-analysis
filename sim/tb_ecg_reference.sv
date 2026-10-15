`timescale 1ns/1ps
// 读取同一组时钟输入，导出 RTL 状态；由 Python 做逐字段比较。
module ecg_reference_driver #(
    parameter integer SAMPLE_WIDTH=16, SAMPLE_RATE_HZ=360, INTEGRATION_MS=120,
    REFRACTORY_MS=200, ENERGY_WIDTH=24,
    INITIAL_NOISE_LEVEL=4096, INITIAL_SIGNAL_LEVEL=16384
);
    reg clk=0; always #5 clk=~clk;
    reg reset_n=0, valid=0;
    reg signed [SAMPLE_WIDTH-1:0] sample=0;
    wire qrs_valid;
    wire [31:0] qrs_index, rr;
    wire [ENERGY_WIDTH-1:0] energy, threshold;
    ecg_qrs_detector #(
        .SAMPLE_WIDTH(SAMPLE_WIDTH), .SAMPLE_RATE_HZ(SAMPLE_RATE_HZ),
        .INTEGRATION_MS(INTEGRATION_MS), .REFRACTORY_MS(REFRACTORY_MS),
        .ENERGY_WIDTH(ENERGY_WIDTH), .INITIAL_NOISE_LEVEL(INITIAL_NOISE_LEVEL),
        .INITIAL_SIGNAL_LEVEL(INITIAL_SIGNAL_LEVEL)
    ) dut(.clk(clk), .rst_n(reset_n), .sample_valid(valid), .sample_in(sample),
          .qrs_valid(qrs_valid), .qrs_sample_index(qrs_index), .rr_interval_samples(rr),
          .integrated_energy(energy), .adaptive_threshold(threshold));
    integer input_fd, output_fd, scanned, r, v, s, cycle=0;
    initial begin
        input_fd=$fopen("vectors.txt","r"); output_fd=$fopen("rtl_trace.csv","w");
        if(!input_fd || !output_fd) $fatal(1,"Cannot open vector/trace file");
        $fwrite(output_fd,"qrs_valid,qrs_sample_index,rr_interval_samples,integrated_energy,adaptive_threshold,noise_level,signal_level,previous_energy,previous_sample,previous_sample_valid,sample_index,refractory_remaining,write_pointer,last_qrs_index,have_last_qrs\n");
        while(!$feof(input_fd)) begin
            scanned=$fscanf(input_fd,"%d %d %d\n",r,v,s);
            if(scanned==3) begin
                @(negedge clk); reset_n=r; valid=v; sample=s;
                @(posedge clk); #1;
                $fwrite(output_fd,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                    qrs_valid,qrs_index,rr,energy,threshold,dut.noise_level,dut.signal_level,
                    dut.previous_energy,dut.previous_sample,dut.previous_sample_valid,
                    dut.sample_index,dut.refractory_remaining,dut.write_pointer,
                    dut.last_qrs_index,dut.have_last_qrs);
                cycle=cycle+1;
            end else if(scanned!=-1) $fatal(1,"Malformed vector");
        end
        $fclose(input_fd); $fclose(output_fd);
        $display("PASS REFERENCE_TRACE cycles=%0d",cycle); $finish;
    end
    initial begin #5000000; $fatal(1,"Reference timeout"); end
endmodule
