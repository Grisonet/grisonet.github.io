import io,zipfile,urllib.request,sys
class R(io.RawIOBase):
    def __init__(s,u):
        s.u=u; s.p=0
        s.n=int(urllib.request.urlopen(urllib.request.Request(u,method="HEAD")).headers["Content-Length"])
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.p
    def seek(s,o,w=0):
        s.p={0:o,1:s.p+o,2:s.n+o}[w]; return s.p
    def read(s,k=-1):
        if k<0: k=s.n-s.p
        if k==0 or s.p>=s.n: return b""
        e=min(s.p+k,s.n)-1
        d=urllib.request.urlopen(urllib.request.Request(s.u,headers={"Range":f"bytes={s.p}-{e}"})).read()
        s.p+=len(d); return d
    def readinto(s,b):
        d=s.read(len(b)); b[:len(d)]=d; return len(d)
u,out=sys.argv[1],sys.argv[2]; sqs=sys.argv[3:]
z=zipfile.ZipFile(io.BufferedReader(R(u),buffer_size=1<<16))
names=z.namelist(); print(len(names),names[:3])
for sq in sqs:
    m=[n for n in names if sq in n]
    print(sq,m)
    for n in m[:1]: open(f"{out}/{sq}.{n.rsplit('.',1)[-1]}","wb").write(z.read(n))
