# 使用原领航者板级配置，仅替换检测器实现；旧工程/硬件保持原位。
set root [file normalize [file join [file dirname [info script]] ..]]
if {$argc != 1} {error "Usage: build_ecg_auto.tcl new_output_directory"}
set output [file normalize [lindex $argv 0]]
if {![string match "${root}/tmp/*" $output]} {error "Output must be inside project tmp"}
if {[file exists $output]} {error "Output exists; refusing overwrite"}
file mkdir $output
# 固定本次源码快照，后续开发改动不能混入正在综合的工程。
set detector_path [file join $output ecg_qrs_auto.sv]
file copy [file join $root src rtl ecg_qrs_auto.sv] $detector_path
set fd [open [file join $root src rtl ecg_qrs_axi_lite.sv] r];set axi [read $fd];close $fd
if {[llength [regexp -all -inline {ecg_qrs_detector #\(} $axi]] != 1} {error "Detector anchor mismatch"}
set axi [string map [list {ecg_qrs_detector #(} {ecg_qrs_auto #(}] $axi]
set axi_path [file join $output ecg_qrs_axi_lite.sv]
set fd [open $axi_path w];puts -nonewline $fd $axi;close $fd
create_project ecg_auto [file join $output vivado] -part xc7z020clg400-2
set fd [open [file join $root build build_navigator_ecg_system.tcl] r];set design [read $fd];close $fd
set design [string map [list \
    {set project_root [file normalize [file join [file dirname [info script]] ..]]} [list set project_root $root] \
    {set rtl_detector [file join $project_root src rtl ecg_qrs_detector.sv]} [list set rtl_detector $detector_path] \
    {set rtl_axi [file join $project_root src rtl ecg_qrs_axi_lite.sv]} [list set rtl_axi $axi_path]] $design]
set ecg_sample_rate_hz 500
eval $design
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {![string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {![string match {*Complete*} [get_property STATUS [get_runs impl_1]]]} {error "Implementation failed"}
open_run impl_1
report_timing_summary -file [file join $output timing.rpt]
report_utilization -file [file join $output utilization.rpt]
# 有bit不代表时序合格；建立/保持失败时保留工程但不导出候选交付。
foreach delay_type {max min} {
    set worst_path [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $worst_path] != 1 || [get_property SLACK $worst_path] < 0} {
        error "Candidate $delay_type timing failed; refusing hardware export"
    }
}
file mkdir [file join $output hardware]
file copy [file join [get_property DIRECTORY [get_runs impl_1]] ecg_system_wrapper.bit] [file join $output hardware ecg_system_candidate.bit]
write_hw_platform -fixed -include_bit -file [file join $output hardware ecg_system_candidate.xsa]
set init [get_files -all -quiet */ps7_init.tcl]
if {[llength $init] != 1} {
    set init [glob -nocomplain [file join $output vivado ecg_auto.gen sources_1 bd ecg_system ip ecg_system_processing_system7_0_0 ps7_init.tcl]]
}
if {[llength $init] != 1} {error "PS init file not unique"}
file copy [lindex $init 0] [file join $output hardware ps7_init.tcl]
puts "ECG_AUTO_HARDWARE_BUILT"
