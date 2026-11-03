# Vivado Tcl Console: 当前设计已打开后运行；不接触下载器、串口或网页。
# set skill_report_dir {<新的输出目录>}
# source {<本脚本绝对路径>}
if {![info exists skill_report_dir]} {error "先设置skill_report_dir为新的输出目录"}
if {[current_design -quiet] eq ""} {error "请先打开需要核查的实现设计"}
set skill_report_target [file normalize $skill_report_dir]
if {[file exists $skill_report_target]} {error "输出已存在，保留原报告，请另选目录"}
file mkdir $skill_report_target
report_utilization -file [file join $skill_report_target utilization.rpt]
report_utilization -hierarchical -file [file join $skill_report_target hierarchy.rpt]
report_timing_summary -file [file join $skill_report_target timing.rpt]
puts "REPORTS_EXPORTED $skill_report_target"
