# 兼容旧文件名：现在使用完整的一次性工程配置脚本。
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir build_ac7020_ecg_system.tcl]
