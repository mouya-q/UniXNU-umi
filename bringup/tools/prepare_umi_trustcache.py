#!/usr/bin/env python3
"""Bundle the selected IPSW's two unchanged static/System trust-cache modules."""
import hashlib
import json
from pathlib import Path
import plistlib
import struct

ROOT=Path(__file__).resolve().parents[2]
sha=lambda b:hashlib.sha256(b).hexdigest()


def der(data,at=0):
    if at+2>len(data):raise ValueError("Truncated DER")
    tag,n=data[at:at+2];at+=2
    if n&128:
        count=n&127
        if not 0<count<=4 or at+count>len(data):raise ValueError("DER length")
        n=int.from_bytes(data[at:at+count],"big");at+=count
    if at+n>len(data):raise ValueError("DER extent")
    return tag,data[at:at+n],at+n


def main():
    folder=ROOT/"out/umi-xnu/ipsw/21H461"
    manifest=plistlib.loads((folder/"BuildManifest.plist").read_bytes())
    assert manifest["ProductBuildVersion"]=="21H461"
    identities=[i for i in manifest["BuildIdentities"] if i["Info"]["DeviceClass"]=="j120ap"]
    assert len(identities)==2
    modules=[];inputs={}
    for name,wanted,kind in (
        ("StaticTrustCache","da88460e6e513438d5307e5c526f76497a74754476a24da29f239f0c90120fc2",b"trst"),
        ("Cryptex1,SystemTrustCache","d121ba89167e03aafd00fa687c30cd8ebc4ccafd10c1408adb2ba3de12403651",b"trcs"),
    ):
        entry=identities[0]["Manifest"][name]
        source=folder/Path(entry["Info"]["Path"]).name
        data=source.read_bytes()
        assert all(i["Manifest"][name]["Digest"]==hashlib.sha384(data).digest() for i in identities)
        tag,sequence,end=der(data);assert tag==0x30 and end==len(data)
        fields=[];at=0
        while at<len(sequence):
            tag,value,at=der(sequence,at);fields.append((tag,value))
        assert [t for t,_ in fields]==[0x16,0x16,0x16,4]
        assert fields[0][1]==b"IM4P" and fields[1][1]==kind
        module=fields[3][1]
        assert sha(module)==wanted and struct.unpack_from("<I",module)[0]==2
        entries=struct.unpack_from("<I",module,20)[0]
        assert len(module)==24+entries*24
        modules.append(module)
        inputs[str(source.relative_to(ROOT))]={"sha256":sha(data),"module_sha256":wanted,"entries":entries}
    bundle=struct.pack("<3I",2,12,12+len(modules[0]))+b"".join(modules)
    assert sha(bundle)=="7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7"
    out=ROOT/"out/umi/trustcache";out.mkdir(parents=True, exist_ok=True)
    target=out/"original-static-system.bundle";target.write_bytes(bundle)
    report={"bundle":str(target),"bundle_sha256":sha(bundle),"bytes":len(bundle),"inputs":inputs,
            "modules_modified":False,"own_entries_added":False,
            "source_sha256":sha(Path(__file__).read_bytes())}
    (out/"inputs.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Verified both original target modules and bundled",len(bundle),"bytes")


if __name__=="__main__":main()