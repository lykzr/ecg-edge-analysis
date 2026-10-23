# 便携JTAG临时运行。必须显式指定已核对的下载器序列号，不操作Flash。
set root [file normalize [file dirname [info script]]]
set bit [file join $root hardware ecg_system_candidate.bit]
set init [file join $root hardware ps7_init.tcl]
set elf [file join $root prebuilt ecg_bridge.elf]
foreach path [list $bit $init $elf] {
    if {![file isfile $path]} {error "Missing file: $path"}
}
if {$argc == 1 && [lindex $argv 0] eq "--check-only"} {
    puts "CHECK_ONLY_PASS: bridge files present; no hardware connection"
    exit 0
}
if {$argc < 1 || $argc > 2} {error "Usage: run_bridge.tcl cable_serial ?server_url?"}
set cable [lindex $argv 0]
if {![regexp {^[A-Za-z0-9_-]+$} $cable]} {error "Invalid cable serial"}
set url "TCP:127.0.0.1:3121"
if {$argc == 2} {set url [lindex $argv 1]}
connect -url $url
# 硬件服务刚建立连接时等待发现；仍以唯一目标校验决定能否配置。
after 2000
set cpus {}; set fpgas {}
foreach target [targets -target-properties] {
    if {[dict exists $target jtag_cable_serial] && [dict get $target jtag_cable_serial] eq $cable} {
        if {[dict get $target name] eq "ARM Cortex-A9 MPCore #0"} {lappend cpus [dict get $target target_id]}
        if {[dict get $target name] eq "xc7z020"} {lappend fpgas [dict get $target target_id]}
    }
}
if {[llength $cpus] != 1 || [llength $fpgas] != 1} {error "Expected one selected cable and Zynq-7020"}
targets -set [lindex $cpus 0]
rst -system
after 3000
fpga -file $bit
source $init
ps7_init
ps7_post_config
targets -set [lindex $cpus 0]
dow $elf
con
puts "ECG_BRIDGE_JTAG_STARTED"
disconnect
