difference(){
union(){
translate([-2.5,0,0]) cube([20,125,3]);
translate([-12.5,0,0]) cube([40,10,9]);
}
translate([15/2,5,0]) cylinder(d=3.3,h=9, $fn=15);
translate([15/2+15,5,0]) cylinder(d=3.3,h=9, $fn=15);
translate([15/2-15,5,0]) cylinder(d=3.3,h=9, $fn=15);
translate([0,0,-3]){
translate([15/2,5,0]) cylinder(d=8.3,h=9, $fn=15);
translate([15/2+15,5,0]) cylinder(d=8.3,h=9, $fn=15);
translate([15/2-15,5,0]) cylinder(d=8.3,h=9, $fn=15);
}
translate([2,38,0]) cube([11,95-41,3]);
translate([15/2,95,0]) cylinder(d=3.3,h=3, $fn=15);
translate([15/2,120,0]) cylinder(d=3.3,h=3, $fn=15);
translate([2,98,0]) cube([11,19,3]);
}