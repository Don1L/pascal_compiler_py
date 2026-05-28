program Optimizations;
var
  x: integer;
  flag: boolean;
begin
  { Constant folding: 2 + 3 * 4 = 14 }
  x := 2 + 3 * 4;
  WriteLn(x);

  { Algebraic simplification: x * 1 = x, x + 0 = x }
  x := x * 1;
  x := x + 0;
  WriteLn(x);

  { not not true = true }
  flag := not not true;
  WriteLn(x);

  { Dead code after break }
  while true do
  begin
    x := x + 1;
    break;
    x := 999;
    WriteLn(999);
  end;
  WriteLn(x);

  { if false → убирается then-ветка }
  if false then
    x := 999;
  WriteLn(x);
end.
