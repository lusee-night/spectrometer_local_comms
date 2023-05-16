import sys
a = int(sys.argv[1])
b = int(sys.argv[2])

c = a * a
d = b * b

e = c + d
f = e >> 31
print(f"{a} corr with {b} is {f} or {hex(f)}")
