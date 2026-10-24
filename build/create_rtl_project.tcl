if {[llength $argv] < 1 || [llength $argv] > 2} {
    puts stderr "用法：vivado -mode batch -source create_rtl_project.tcl -tclargs <Vivado器件完整型号> ?新输出目录?"
    exit 2
}

set device_part [lindex $argv 0]
set script_dir [file dirname [file normalize [info script]]]
set project_root [file normalize [file join $script_dir ..]]
set project_dir [file join $project_root tmp vivado ecg_edge]
if {[llength $argv] == 2} { set project_dir [file normalize [lindex $argv 1]] }
set rtl_file [file join $project_root src rtl ecg_qrs_detector.sv]

if {![file isfile $rtl_file]} {
    error "找不到 RTL 源文件：$rtl_file"
}

if {[file exists $project_dir]} {
    error "工程目录已存在，为避免覆盖，停止创建：$project_dir"
}

file mkdir [file dirname $project_dir]
create_project ecg_edge $project_dir -part $device_part
# 模块引用需要先加入全部依赖并确定语言，再选择顶层；避免缓存不完整层次。
set rtl_files [list $rtl_file [file join $project_root src rtl ecg_qrs_axi_lite.sv]]
foreach path $rtl_files {if {![file isfile $path]} {error "缺少RTL：$path"}}
add_files -norecurse $rtl_files
foreach path $rtl_files {set_property file_type SystemVerilog [get_files $path]}
set_property top ecg_qrs_axi_lite [current_fileset]
update_compile_order -fileset sources_1
source [file join $script_dir build_navigator_ecg_system.tcl]

puts "已为器件 $device_part 创建领航者 ECG 完整 PS7/AXI 工程：$project_dir"
puts "本脚本未运行综合、仿真或 bitstream 生成。"
