# 使用 AMD Tcl XSDB；每次重新复位系统并配置 PL，仅 JTAG 临时运行。
set kit_root [file normalize [file dirname [info script]]]
set bit_file [file join $kit_root hardware ecg_system_candidate.bit]
set init_file [file join $kit_root hardware ps7_init.tcl]
set elf_file [file join $kit_root prebuilt ecg_smoke.elf]
foreach path [list $bit_file $init_file $elf_file] {
    if {![file isfile $path]} {error "Missing file: $path"}
}
if {$argc == 1 && [lindex $argv 0] eq "--check-only"} {
    puts "CHECK_ONLY_PASS: files present; no hardware connection"
    exit 0
}
set server_url "TCP:127.0.0.1:3121"
if {$argc == 1} {set server_url [lindex $argv 0]}
if {$argc > 1} {error "Usage: run_smoke.tcl ?server_url|--check-only?"}
connect -url $server_url
# 不自动在多板目标间选择，匹配不唯一时 targets -set 自行报错。
targets -set -nocase -filter {name =~ "ARM*#0"}
rst -system
after 3000
fpga -file $bit_file
source $init_file
ps7_init
ps7_post_config
targets -set -nocase -filter {name =~ "ARM*#0"}
dow $elf_file
con
puts "JTAG launched; inspect UART for PASS ECG_SMOKE failures=0"
disconnect
