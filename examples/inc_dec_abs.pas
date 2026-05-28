program IncDecAbs;
var
  x: integer;
begin
  x := 5;
  Inc(x);
  Inc(x);
  WriteLn(x);
  Dec(x);
  WriteLn(x);
  x := -10;
  WriteLn(Abs(x));
end.
