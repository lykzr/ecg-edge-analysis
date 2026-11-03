# 仅导出已布线候选的真实资源，不计算估算减量。
if {$argc!=2} {error "参数：候选工程目录 JSON输出路径"}
lassign $argv out result
open_project [file normalize $out]/cnn_pl.xpr
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "候选尚未实现完成"}
open_run impl_1
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0 || [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]<0} {error "候选时序不通过"}
proc usage {cells} {
    set report [report_utilization -cells $cells -return_string]
    set values {}
    foreach label {{Slice LUTs} {Slice Registers} {Block RAM Tile} DSPs} {
        set expression [format {\| +%s +\| +([0-9.]+) +\|} $label]
        if {![regexp $expression $report match value]} {error "资源报告缺字段：$label"}
        lappend values $value
    }
    lassign $values lut ff bram dsp
    return "\"lut\":$lut,\"ff\":$ff,\"bram36\":$bram,\"dsp\":$dsp"
}
# 各核及系统均使用Vivado report_utilization同一口径。
set rows {}
foreach {name pattern} {FP32-CNN *ecg_cnn_0 INT8-CNN *ecg_cnn_int8_0} {
    set cells [get_cells -hierarchical -filter "NAME =~ $pattern"]
    if {![llength $cells]} {error "CNN层级缺失：$name"}
    lappend rows "\{\"name\":\"$name\",\"scope\":\"CNN routed utilization\",[usage $cells]\}"
}
lappend rows "\{\"name\":\"Three-core system\",\"scope\":\"QRS + HGB + FP32 CNN + INT8 CNN + AXI\",[usage [get_cells -hierarchical -filter {NAME !~ */*}]]\}"
set f [open $result w]
puts $f "\{\"device\":\"xc7z020clg400-2\",\"stage\":\"routed\",\"board_verified\":false,\"capacity\":\{\"lut\":53200,\"ff\":106400,\"bram36\":140,\"dsp\":220\},\"rows\":\[[join $rows ,]\],\"note\":\"Vivado routed report_utilization; FP32 and INT8 use different parallelism. Board verification pending.\"\}"
close $f
