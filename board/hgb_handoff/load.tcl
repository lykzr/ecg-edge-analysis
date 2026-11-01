# 复用自检入口的唯一目标核验和立即停核下载；仅运行独立收样程序。
if {$argc!=4} {error "Usage: load.tcl cable bit init elf"}
lassign $argv cable bit init elf
foreach p [list $bit $init $elf] {if {![file isfile $p]} {error "Missing artifact"}}
connect -url TCP:127.0.0.1:3121
after 1000
set cpus {};set fpgas {};set cables {}
foreach t [targets -target-properties] {
 if {![dict exists $t jtag_cable_serial]} {continue}
 set serial [dict get $t jtag_cable_serial];lappend cables $serial
 if {$serial ne $cable} {continue}
 if {[dict get $t name] eq "ARM Cortex-A9 MPCore #0"} {lappend cpus [dict get $t target_id]}
 if {[dict get $t name] eq "xc7z020"} {lappend fpgas [dict get $t target_id]}
}
if {[llength [lsort -unique $cables]]!=1 || [llength $cpus]!=1 || [llength $fpgas]!=1} {error "Expected unique Zynq-7020"}
targets -set [lindex $cpus 0]
rst -system -stop
after 1000
rst -processor
after 1000
fpga -file $bit
source $init
ps7_init
ps7_post_config
dow $elf
con
puts "PASS HGB_BATCH_JTAG_STARTED"
disconnect
