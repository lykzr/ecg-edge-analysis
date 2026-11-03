# 在Vivado Tcl Console中source本文件，打开原始布局布线检查点，不连接板卡。
set bundle [file dirname [file normalize [info script]]]
open_checkpoint [file join $bundle routed.dcp]
report_utilization -name System_Resource_Utilization
report_utilization -hierarchical -hierarchical_depth 3 -name CNN_Resource_Comparison
report_timing_summary -name Implemented_Timing
