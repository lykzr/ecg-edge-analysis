# 从正式源码重建当前360Hz硬件；不下载，不改PS7/MIO/XDC或旧工程。
set rebuild_root [file normalize [file join [file dirname [info script]] ..]]
if {[llength $argv] != 1} {error "指定新的项目tmp输出目录"}
set rebuild_out [file normalize [lindex $argv 0]]
if {[string first "[file join $rebuild_root tmp]/" "$rebuild_out/"] != 0 || [file exists $rebuild_out]} {error "输出须为新的项目tmp目录"}
set ecg_sample_rate_hz 360
# 复用本轮原生成功构建的同一入口，不维护第二套工程初始化。
set rebuild_args $argv
set argv [list xc7z020clg400-2 [file join $rebuild_out vivado]]
source [file join $rebuild_root build create_rtl_project.tcl]
set argv $rebuild_args
set rebuild_hw [file join $rebuild_out hardware]
file mkdir $rebuild_hw
# 源配置完全复用原脚本，额外导出BD供逐项参数核对。
file copy [get_property NAME [lindex [get_files -quiet *ecg_system.bd] 0]] [file join $rebuild_hw ecg_system.bd]
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "综合未完成"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "实现/bitstream未完成"}
open_run impl_1
report_timing_summary -file [file join $rebuild_hw timing.rpt]
report_utilization -file [file join $rebuild_hw utilization.rpt]
# 实现流程已执行DRC；保存同一布线运行的报告，避免再次启动全量规则扫描。
set routed_drc [file join $rebuild_out vivado ecg_edge.runs impl_1 ecg_system_wrapper_drc_routed.rpt]
if {![file isfile $routed_drc]} {error "缺少实现DRC报告"}
file copy $routed_drc [file join $rebuild_hw drc.rpt]
set setup_path [get_timing_paths -max_paths 1 -setup]
set hold_path [get_timing_paths -max_paths 1 -hold]
if {![llength $setup_path] || ![llength $hold_path]} {error "缺少可核对时序路径"}
set fd [open [file join $rebuild_hw timing.tsv] w]
puts $fd "setup_slack_ns\t[get_property SLACK $setup_path]"
puts $fd "hold_slack_ns\t[get_property SLACK $hold_path]"
close $fd
if {[get_property SLACK $setup_path] < 0 || [get_property SLACK $hold_path] < 0} {error "时序未收敛"}
write_hw_platform -fixed -include_bit -file [file join $rebuild_hw ecg_system_candidate.xsa]
foreach pair [list [list [file join $rebuild_out vivado ecg_edge.runs impl_1 ecg_system_wrapper.bit] ecg_system_candidate.bit] [list [file join $rebuild_out vivado ecg_edge.gen sources_1 bd ecg_system ip ecg_system_processing_system7_0_0 ps7_init.tcl] ps7_init.tcl]] {
 if {![file isfile [lindex $pair 0]]} {error "缺匹配产物：[lindex $pair 0]"}
 file copy [lindex $pair 0] [file join $rebuild_hw [lindex $pair 1]]
}
close_project
puts "PASS REBUILD_HARDWARE; no board operation"
exit 0
