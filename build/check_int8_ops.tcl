# 独立算子综合；不读/修改主工程、PS7、XDC或板卡。
set root [file normalize [file join [file dirname [info script]] ..]]
if {![info exists ::env(ECG_OPS_OUTPUT)]} {error "指定ECG_OPS_OUTPUT为新的tmp目录"}
set output [file normalize $::env(ECG_OPS_OUTPUT)]
set prefix "[file normalize [file join $root tmp]]/"
if {[string first $prefix "$output/"] != 0 || [file exists $output]} {error "输出须为新的项目tmp目录"}
file mkdir $output
read_verilog -sv [file join $root src rtl ecg_int8_ops.sv]
synth_design -mode out_of_context -top ecg_int8_conv -part xc7z020clg400-2
report_utilization -file [file join $output utilization.rpt]
write_checkpoint [file join $output operator.dcp]
puts "PASS INT8_SYNTH_ONLY; NOT IMPLEMENTATION OR TIMING OR BOARD"
