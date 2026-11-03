# 领航者V2底板PL_LED0；官方1_led例程：H15/LVCMOS33，高有效。
# 核心板2V5第3/7页：BANK35，VCCO_B35由3.3V的0R电阻供电。
set_property -dict {PACKAGE_PIN H15 IOSTANDARD LVCMOS33 DRIVE 4 SLEW SLOW} [get_ports work_led]
