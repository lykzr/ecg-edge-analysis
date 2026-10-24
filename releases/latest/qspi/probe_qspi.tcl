# 只读取唯一已指定Zynq和BOOT_MODE；不下载程序，不改启动寄存器。
if {$argc!=2} {error "Usage: probe_qspi.tcl cable expected_boot_mode"}
lassign $argv cable mode
if {![regexp {^[A-Za-z0-9_-]+$} $cable] || $mode ni {0 1}} {error "Invalid identity or boot mode"}
connect -url TCP:127.0.0.1:3121
after 1000
set cpus {};set fpgas {};set cables {};set flash_target ""
foreach t [targets -target-properties] {
 if {![dict exists $t jtag_cable_serial]} {continue}
 set serial [dict get $t jtag_cable_serial];lappend cables $serial
 if {$serial ne $cable} {continue}
 if {[dict get $t name] eq "ARM Cortex-A9 MPCore #0"} {
  lappend cpus [dict get $t target_id];set flash_target [dict get $t jtag_device_ctx]
 }
 if {[dict get $t name] eq "xc7z020"} {lappend fpgas [dict get $t target_id]}
}
if {[llength [lsort -unique $cables]]!=1 || [llength $cpus]!=1 || [llength $fpgas]!=1} {error "Expected unique selected Zynq-7020"}
targets -set [lindex $cpus 0]
set actual [expr {[mrd -value 0xF800025C] & 15}]
puts "BOOT_MODE=$actual"
if {$actual!=$mode} {error "Physical boot switch/power cycle required; expected mode $mode"}
puts "FLASH_TARGET=$flash_target"
puts "CPU_TARGET=[lindex $cpus 0]"
disconnect
