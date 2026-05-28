program Variables;
var
  x: integer;
  y: integer;
  flag: boolean;
begin
  x := 10;
  y := x + 5 * 2;
  flag := y > 15;
  WriteLn(x);
  WriteLn(y);
end.
