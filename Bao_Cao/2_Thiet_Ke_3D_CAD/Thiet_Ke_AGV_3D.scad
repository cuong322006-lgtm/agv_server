// ============================================================================
// BẢN VẼ 3D CAD CHI TIẾT KIỂU INVENTOR (OPENSCAD / FREECAD)
// Khung Sắt V Lỗ Đa Năng (Có Hốc Rãnh Bánh Xe Tải) + Mâm Xoay Bi Sắt Vuông 71x71mm
// + 4x Servo MG996R (40.3x20x36.6mm) + Bo Mạch PCB 150x90mm (Lỗ M3 140x80mm)
// Đơn vị: milimét (mm)
// ============================================================================

total_L        = 350;   // Chiều dài khung xe (350 mm)
total_W        = 250;   // Chiều rộng phủ bì khung (250 mm)
well_depth     = 45;    // Độ sâu hốc rãnh bánh xe âm vào thân khung (45 mm)
well_length    = 96;    // Chiều dài hốc rãnh chứa bánh xe 80mm (96 mm)
cab_L          = 100;   // Chiều dài khung Cabin đầu xe (100 mm)
cab_H          = 100;   // Chiều cao khung Cabin (100 mm)
wall_H         = 50;    // Chiều cao thành khung thùng hàng (50 mm)
vbar_size      = 25;    // Bản rộng thanh Sắt V lỗ (25 mm)
vbar_thick     = 2.0;   // Độ dày thanh Sắt V lỗ (2 mm)
turntable_size = 71;    // Mâm xoay sắt mạ có bi vuông 3 Inch (71x71 mm)

ground_clear   = 30;
bay_H          = 45;
bed_Z          = ground_clear + bay_H;
roof_Z         = bed_Z + cab_H;

$fn = 40;

// 1. Module Thanh Sắt V Lỗ Đa Năng (L-Angle Slotted Bar có đục lỗ bầu dục/tròn)
module slotted_vbar(len, s = vbar_size, t = vbar_thick) {
    color([0.23, 0.27, 0.32])
    difference() {
        union() {
            cube([len, s, t]);
            cube([len, t, s]);
        }
        // Đục dãy lỗ dọc theo 2 cánh chữ V (bước lỗ 20mm)
        for (x = [12 : 20 : len - 12]) {
            translate([x, s/2 + 2, -1]) cylinder(h = t + 2, d = 6.5);
            translate([x, -1, s/2 + 2]) rotate([-90, 0, 0]) cylinder(h = t + 2, d = 6.5);
        }
    }
}

// 2. Module Động cơ RC Servo MG996R chuẩn bản vẽ (40.3 x 20.0 x 36.6 mm, tai 53.6 mm)
module servo_mg996r() {
    union() {
        color([0.15, 0.17, 0.2]) {
            translate([-20.15, -10, 0]) cube([40.3, 20.0, 36.6]);
            translate([-26.8, -9.75, 26.6]) cube([53.6, 19.5, 2.5]);
            translate([10, 0, 36.6]) cylinder(h = 4, d = 12);
        }
        // Nhông đồng 25T (Tổng chiều cao 47.6 mm)
        color("Gold") translate([10, 0, 40.6]) cylinder(h = 7, d = 6);
    }
}

// 3. Module Mâm Xoay Bằng Sắt Mạ Có Bi Vuông (3 Inch: 71x71mm)
module lazy_susan_turntable(sz = turntable_size, yaw_deg = 0) {
    color("Silver") {
        // Tấm vuông dưới cố định
        translate([-sz/2, -sz/2, 0]) cube([sz, sz, 2.2]);
        // Vòng rãnh bi tròn ở giữa
        translate([0, 0, 2.2]) cylinder(h = 3.5, d = sz * 0.75);
        // Tấm vuông trên xoay theo cánh tay
        rotate([0, 0, 45 + yaw_deg])
        translate([-sz/2, -sz/2, 5.7]) cube([sz, sz, 2.2]);
    }
}

// 4. Module Bo Mạch PCB Chính 150x90mm (Đúng tọa độ lỗ khoan Gerber 140x80mm)
module pcb_150x90_altium() {
    difference() {
        color("SeaGreen") cube([150, 90, 1.6]);
        for (px = [5, 145]) for (py = [5, 85])
            translate([px, py, -1]) cylinder(h = 4, d = 3.2);
    }
    // ESP32-S3 ở giữa, 2x TB6612 bên trái, 2x LM2596 bên dưới, PCA9685 bên phải
    color([0.1, 0.1, 0.1]) translate([61, 20, 1.6]) cube([28, 62, 12]);
    color("Crimson") translate([18, 22, 1.6]) cube([21, 21, 10]);
    color("Crimson") translate([18, 52, 1.6]) cube([21, 21, 10]);
    color("RoyalBlue") translate([14, 4, 1.6]) cube([43, 21, 11]);
    color("RoyalBlue") translate([93, 4, 1.6]) cube([43, 21, 11]);
    color("MediumBlue") translate([118, 20, 1.6]) cube([25, 62, 10]);
}

// 5. Tổng lắp ráp Khung Sắt V Lỗ Có Hốc Bánh Xe & Cánh Tay MG996R
module agv_inventor_assembly() {
    inner_W = total_W - 2 * well_depth; // 160 mm (Tạo 4 hốc bánh xe sâu 45mm ở 2 bên!)

    // A. 2 Thanh dầm dọc chính dưới gầm (Thu hẹp vào giữa để chừa 4 rãnh hốc bánh xe 80mm)
    translate([0, well_depth, ground_clear]) slotted_vbar(total_L);
    translate([0, total_W - well_depth - vbar_size, ground_clear]) slotted_vbar(total_L);

    // B. 4 Thanh dầm ngang gầm tạo vách chắn trước/sau cho 4 Hốc Rãnh Bánh Xe
    for (cx = [0, 65 + well_length/2, total_L - 65 - well_length/2 - vbar_size, total_L - vbar_size]) {
        translate([cx + vbar_size, 0, ground_clear])
        rotate([0, 0, 90]) slotted_vbar(total_W);
    }

    // C. Khung tầng sàn thùng trên (Chạy suốt bề rộng 250mm phía trên 4 hốc bánh xe)
    translate([0, 0, bed_Z - vbar_size]) slotted_vbar(total_L);
    translate([0, total_W - vbar_size, bed_Z - vbar_size]) slotted_vbar(total_L);

    // D. 4 Trụ đứng Cabin & Khung dầm nóc Cabin đỡ Mâm Xoay Bi Sắt
    for (cx = [0, cab_L - vbar_size]) for (cy = [0, total_W - vbar_size]) {
        translate([cx, cy, bed_Z])
        rotate([0, -90, 0]) slotted_vbar(cab_H);
    }
    translate([0, 0, roof_Z - vbar_size]) slotted_vbar(cab_L);
    translate([0, total_W - vbar_size, roof_Z - vbar_size]) slotted_vbar(cab_L);

    // E. Cụm Mâm Xoay Bi Sắt 71x71mm + Servo MG996R 360° dưới gầm + Cánh Tay 3xMG996R 180°
    translate([45, total_W/2, roof_Z]) {
        lazy_susan_turntable(turntable_size, 0);
        translate([-10, 0, -40]) servo_mg996r(); // MG996R 360° dưới mâm xoay
        translate([-10, 0, 10]) servo_mg996r();  // MG996R 180° #1 (Khớp Vai)
    }

    // F. Bo mạch PCB 150x90mm đặt trên dầm gầm giữa
    translate([cab_L + 25, (total_W - 90)/2, ground_clear + 14])
    pcb_150x90_altium();
}

agv_inventor_assembly();
