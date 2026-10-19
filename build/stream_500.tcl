# 构建独立500Hz合成流硬件；不改360Hz共享工程、smoke发布或板卡。
set stream_script_dir [file dirname [file normalize [info script]]]
set stream_root [file normalize [file join $stream_script_dir ..]]
if {[llength $argv] > 1} {error "用法：-source build/stream_500.tcl -tclargs ?新输出目录?"}
set stream_output [file join $stream_root tmp ecg_stream_500]
if {[llength $argv]} {set stream_output [file normalize [lindex $argv 0]]}
if {[file exists $stream_output]} {error "输出目录已存在，停止避免覆盖：$stream_output"}
set ecg_sample_rate_hz 500
set argv [list xc7z020clg400-2 [file join $stream_output vivado]]
source [file join $stream_script_dir create_rtl_project.tcl]
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "综合未完成"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "实现/bitstream未完成"}
open_run impl_1
set hardware [file join $stream_output hardware]
file mkdir $hardware
report_timing_summary -file [file join $hardware timing.rpt]
report_utilization -file [file join $hardware utilization.rpt]
write_hw_platform -fixed -include_bit -file [file join $hardware ecg_system_candidate.xsa]
set bit [file join $stream_output vivado ecg_edge.runs impl_1 ecg_system_wrapper.bit]
set psinit [file join $stream_output vivado ecg_edge.gen sources_1 bd ecg_system ip ecg_system_processing_system7_0_0 ps7_init.tcl]
foreach path [list $bit $psinit] {if {![file isfile $path]} {error "缺少匹配产物：$path"}}
file copy $bit [file join $hardware ecg_system_candidate.bit]
file copy $psinit [file join $hardware ps7_init.tcl]
close_project
puts "PASS STREAM_500_HARDWARE_BUILT $hardware; not a board test"
exit 0
