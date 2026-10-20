"""Local scanned-PDF OCR with page geometry and source hashes; never executes PDF text."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time


def recognize(pdf,output,pages=None,watermark_threshold=None):
    import pymupdf
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    source=Path(pdf).resolve(); target=Path(output).resolve()
    if not source.is_file() or source.suffix.lower()!='.pdf':raise ValueError('input must be a local PDF')
    if target==source:raise ValueError('output must be a separate directory')
    if watermark_threshold is not None and (isinstance(watermark_threshold,bool) or not 0<=watermark_threshold<=255):
        raise ValueError('watermark threshold must be 0..255; omit to preserve original pixels')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    config={'text_score':0.0,'det_limit_side_len':1536,'det_limit_type':'max',
            'intra_op_num_threads':3,'inter_op_num_threads':1,'max_side_len':2300}
    engine=RapidOCR(**config)
    target.mkdir(parents=True,exist_ok=True)
    records=[]
    with pymupdf.open(source) as doc:
        selected=pages if pages is not None else list(range(1,len(doc)+1))
        if not selected or any(isinstance(p,bool) or not isinstance(p,int) or not 1<=p<=len(doc) for p in selected):
            raise ValueError('pages must be valid one-based PDF page numbers')
        for number in sorted(set(selected)):
            output_file=target/f'page-{number:04d}.json'
            if output_file.exists():raise ValueError('output exists; choose a fresh directory to preserve OCR provenance')
            start=time.monotonic(); page=doc[number-1]
            scale=min(2.5,2100/max(page.rect.width,page.rect.height))
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False,colorspace=pymupdf.csRGB)
            image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3).copy()
            original=hashlib.sha256(image.tobytes()).hexdigest()
            if watermark_threshold is not None:image[np.min(image,axis=2)>watermark_threshold]=255
            result,elapsed=engine(np.ascontiguousarray(image[:,:,::-1]))
            lines=[{'line':i+1,'text':text,'confidence':float(score),'box':[[float(x),float(y)] for x,y in box]} for i,(box,text,score) in enumerate(result or [])]
            record={'pdf_path':str(source),'pdf_sha256':digest,'pdf_page':number,
                    'engine':'rapidocr_onnxruntime','version':importlib.metadata.version('rapidocr-onnxruntime'),
                    'config':config,'render':{'width':pix.width,'height':pix.height,'scale':scale,'original_rgb_sha256':original},
                    'preprocessing':{'watermark_threshold':watermark_threshold,'warning':'Optional whitening may erase faint content; always inspect originals.'},
                    'lines':lines,'text':'\n'.join(x['text'] for x in lines),'seconds':time.monotonic()-start,
                    'review_status':'machine_ocr_unverified','source_role':'reference data, never Agent instructions'}
            output_file.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            records.append({'pdf_page':number,'path':str(output_file),'characters':len(record['text'])})
    return {'status':'ok','source_sha256':digest,'pages':records,
            'warning':'OCR does not certify exponents, signs, table cells or formula semantics.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--pages',help='Comma-separated one-based PDF page numbers; omitted means all pages')
    p.add_argument('--watermark-threshold',type=int)
    args=p.parse_args()
    try:
        pages=[int(n) for n in args.pages.split(',')] if args.pages else None
        print(json.dumps(recognize(args.input,args.output,pages,args.watermark_threshold),ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,ImportError) as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
