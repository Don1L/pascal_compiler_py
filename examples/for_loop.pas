program ForLoop;
var
  i: integer;
  s: integer;
begin
  s := 0;
  for i := 1 to 10 do
    s := s + i;
  WriteLn(s);
end.
