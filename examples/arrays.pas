program Arrays;
var
  a: array[1..5] of integer;
  i: integer;
  s: integer;
begin
  for i := 1 to 5 do
    a[i] := i * i;
  s := 0;
  for i := 1 to 5 do
    s := s + a[i];
  WriteLn(s);
end.
