# 只触发QSPI系统复位；不执行fpga、ps7_init或dow，不替代冷启动验收。
if {$argc!=1} {error "Usage: reset_qspi.tcl cable"}
set cable [lindex $argv 0]
set base [file dirname [file normalize [info script]]]
set argv [list $cable 1];set argc 2
source [file join $base probe_qspi.tcl]
connect -url TCP:127.0.0.1:3121
targets -set [lindex $cpus 0]
rst -system
after 1000
catch {con}
puts "QSPI_SYSTEM_RESET_NO_IMAGE_DOWNLOAD"
disconnect
