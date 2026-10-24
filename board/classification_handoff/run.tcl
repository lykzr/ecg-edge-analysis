# 仅临时JTAG；调用方已核清单和UART身份，本脚本再次核唯一JTAG目标。
if {$argc!=4} {error "Usage: run.tcl cable bit init elf"}
lassign $argv cable bit init elf
if {![regexp {^[A-Za-z0-9_-]+$} $cable]} {error "Invalid cable"}
foreach p [list $bit $init $elf] {if {![file isfile $p]} {error "Missing artifact: $p"}}
connect -url TCP:127.0.0.1:3121
after 2000
set cpus {};set fpgas {};set cables {}
foreach t [targets -target-properties] {
 if {![dict exists $t jtag_cable_serial]} {continue}
 set serial [dict get $t jtag_cable_serial];lappend cables $serial
 if {$serial ne $cable} {continue}
 if {[dict get $t name] eq "ARM Cortex-A9 MPCore #0"} {lappend cpus [dict get $t target_id]}
 if {[dict get $t name] eq "xc7z020"} {lappend fpgas [dict get $t target_id]}
}
if {[llength [lsort -unique $cables]]!=1 || [llength $cpus]!=1 || [llength $fpgas]!=1} {error "Expected unique selected Zynq-7020"}
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
puts "ECG_CLASS_JTAG_STARTED"
disconnect
