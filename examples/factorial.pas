program Factorial;
var
  n: integer;
  result: integer;

function fact(n: integer): integer;
begin
  if n <= 1 then
    fact := 1
  else
    fact := n * fact(n - 1);
end;

begin
  n := 6;
  WriteLn(fact(n));
end.
