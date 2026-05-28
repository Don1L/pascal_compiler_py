program Procedures;
var
  n: integer;

procedure printLine(x: integer);
begin
  WriteLn(x);
end;

function square(x: integer): integer;
begin
  square := x * x;
end;

begin
  for n := 1 to 5 do
    printLine(square(n));
end.
