"""Private subprocess entry point. No app/settings/database imports or logging."""
import json
import os
from pathlib import Path
import sys


def validate(source, target, media):
    # Limits are installed before this function and before native parser imports.
    import socket
    def denied(*args, **kwargs): raise ValueError('Network unavailable')
    socket.socket.connect=denied; socket.create_connection=denied
    if media.startswith('image/'):
        import warnings
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS=20_000_000
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        expected='JPEG' if media=='image/jpeg' else 'PNG'
        with Image.open(source) as image:
            if image.format!=expected or image.width*image.height>20_000_000 or getattr(image,'n_frames',1)!=1:
                raise ValueError()
            image.verify()
        with Image.open(source) as image:
            image.load()
            image=ImageOps.exif_transpose(image).convert('RGB')
            # Copy pixels into a fresh object; no EXIF, ICC, comments or original metadata.
            clean=Image.new('RGB',image.size); clean.paste(image)
            clean.save(target,format=expected)
    else:
        import pymupdf
        import re
        forbidden=re.compile(r'/(?:JavaScript|JS|Launch|OpenAction|AA|EmbeddedFile|Filespec|RichMedia|XFA|AcroForm|URI|GoToR|SubmitForm|ImportData|Sound|Movie|3D|Sig)\b')
        # Conservative supported subset: static scanned/text PDFs. Reject active
        # content rather than attempting to make scripts or attachments safe.
        with pymupdf.open(source) as pdf:
            if not pdf.is_pdf or pdf.needs_pass or pdf.is_encrypted or pdf.is_repaired or not 1<=len(pdf)<=10 or pdf.xref_length()>20000:
                raise ValueError()
            for xref in range(1,pdf.xref_length()):
                obj=pdf.xref_object(xref,compressed=False)
                if '#' in obj or forbidden.search(obj): raise ValueError()
            output=pymupdf.open()
            pixels=0
            try:
                for page in pdf:
                    if list(page.annots() or []) or list(page.widgets() or []) or page.get_links(): raise ValueError()
                    rect=page.rect
                    if rect.is_infinite or rect.is_empty or rect.width>3000 or rect.height>3000: raise ValueError()
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(1,1),alpha=False,colorspace=pymupdf.csRGB)
                    pixels+=pix.width*pix.height
                    if pix.width*pix.height>20_000_000 or pixels>40_000_000: raise ValueError()
                    clean=output.new_page(width=rect.width,height=rect.height)
                    clean.insert_image(clean.rect,stream=pix.tobytes('jpeg'))
                output.set_metadata({})
                output.save(target,garbage=4,deflate=True)
            finally: output.close()
    if not 0<Path(target).stat().st_size<=5*1024*1024: raise ValueError()


def main():
    try:
        if os.name=='posix':
            import importlib.util
            spec=importlib.util.spec_from_file_location('limits',Path(__file__).with_name('driver_document_limits.py'))
            limits=importlib.util.module_from_spec(spec); spec.loader.exec_module(limits)
            limits.posix_limits()
        # Windows parent assigns the Job before sending this input. No document
        # parsing takes place until that handshake has completed.
        request=json.loads(sys.stdin.buffer.readline(8192))
        if set(request)!={'source','target','media'} or request['media'] not in ('image/jpeg','image/png','application/pdf'): raise ValueError()
        validate(**request)
        print('VALIDATED')
        return 0
    except BaseException:
        print('REJECTED')
        return 1


if __name__=='__main__': sys.exit(main())
