# 仅恢复因主机资源故障中止的候选；保留原日志，不改已验镜像。
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc!=1} {error "参数：tmp下候选工程目录"}
set out [file normalize [lindex $argv 0]]
if {![string match "${root}/tmp/*" $out]} {error "必须为tmp候选"}
open_project $out/cnn_pl.xpr
foreach run [get_runs *_synth_1] {
    if {[get_property PROGRESS $run] ne "100%"} {reset_run $run}
}
reset_run synth_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "综合失败"}
open_run synth_1
report_utilization -hierarchical -file $out/synthesis_hierarchy.rpt
close_design
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "实现失败"}
open_run impl_1
report_utilization -file $out/utilization.rpt
report_utilization -hierarchical -file $out/utilization_hierarchy.rpt
report_timing_summary -file $out/timing.rpt
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0 || [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]<0} {error "时序未收敛"}
write_hw_platform -fixed -include_bit -file $out/cnn_pl.xsa
file copy [get_property DIRECTORY [get_runs impl_1]]/ecg_system_wrapper.bit $out/cnn_pl.bit
puts "PASS CNN_INT8_PL_BITSTREAM $out"
