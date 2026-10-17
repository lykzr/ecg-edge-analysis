# 在正式目录建立可共享的Vivado工程；不移动旧工作区、不综合/下载。
set share_script_dir [file dirname [file normalize [info script]]]
set share_root [file normalize [file join $share_script_dir ..]]
if {[llength $argv] > 1} { error "用法：-source build/share.tcl -tclargs ?新输出目录?" }
set share_output [file join $share_root vivado ecg_edge]
if {[llength $argv] == 1} {set share_output [file normalize [lindex $argv 0]]}
set argv [list xc7z020clg400-2 $share_output]
source [file join $share_script_dir create_rtl_project.tcl]
# wrapper不能只放在被忽略的.gen里，否则克隆后顶层缺失。
set share_old_wrapper [require_one [get_files -quiet *ecg_system_wrapper.v] "生成的wrapper"]
set share_hdl [file join $share_output ecg_edge.srcs sources_1 hdl]
file mkdir $share_hdl
set share_wrapper [file join $share_hdl ecg_system_wrapper.v]
if {[file exists $share_wrapper]} {error "wrapper目标已存在，停止而不覆盖"}
file copy $share_old_wrapper $share_wrapper
remove_files $share_old_wrapper
add_files -norecurse $share_wrapper
set_property top ecg_system_wrapper [current_fileset]
update_compile_order -fileset sources_1
close_project
puts "PASS SHARE_PROJECT_CREATED $share_output"
exit 0
