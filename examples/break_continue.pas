program BreakContinue;
var
  i: integer;
begin
  i := 0;
  while true do
  begin
    i := i + 1;
    if i mod 2 = 0 then
      continue;
    if i > 7 then
      break;
    WriteLn(i);
  end;
end.
