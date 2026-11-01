# 独立HGB验收：唯一目标、匹配镜像临时JTAG；不写Flash。
if {$argc!=7} {error "Usage: run.tcl cable bit init elf status_address dumps output"}
lassign $argv cable bit init elf status_address dumps output
if {![regexp {^[A-Za-z0-9_-]+$} $cable] || ![regexp {^0x[0-9a-fA-F]+$} $status_address]} {error "Invalid target or address"}
foreach p [list $bit $init $elf $dumps] {if {![file isfile $p]} {error "Missing artifact $p"}}
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
puts "BOOT_MODE_BEFORE=[mrd -value 0xF800025C]"
# 系统复位后立即停核，避免QSPI旧固件先运行并留下缓存/内存状态。
rst -system -stop
after 1000
rst -processor
after 1000
fpga -file $bit
source $init
ps7_init
ps7_post_config
targets -set [lindex $cpus 0]
dow $elf
con
set done 0
for {set i 0} {$i<240} {incr i} {
 after 500
 set state [expr {[mrd -value [expr {$status_address+4}]] & 0xffffffff}]
 if {$state==1} {set done 1;break}
 if {$state>0x7fffffff} {error "ARM test failed state=$state"}
}
if {!$done} {error "ARM test timed out"}
stop
set f [open $dumps r]
foreach row [split [read $f] "\n"] {
 if {[string trim $row] eq ""} {continue}
 lassign $row name address words
 if {![regexp {^[a-z_]+[.]bin$} $name] || ![regexp {^0x[0-9a-fA-F]+$} $address] || ![string is integer -strict $words] || $words<1} {error "Invalid dump request"}
 mrd -bin -file [file join $output $name] $address $words
 puts "DUMPED $name words=$words"
}
close $f
puts "PASS HGB_ARM_EXECUTED_AND_DUMPED"
disconnect
