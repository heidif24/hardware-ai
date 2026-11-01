import os,httpx,base64
from typing import Any
async def search_components(query:str,limit:int=8)->dict[str,Any]:
 results=[];providers={"mouser":bool(os.getenv("MOUSER_API_KEY")),"digikey":bool(os.getenv("DIGIKEY_CLIENT_ID") and os.getenv("DIGIKEY_CLIENT_SECRET")),"lcsc":"catalogue_linkout"}
 if providers["mouser"]:
  try:
   async with httpx.AsyncClient(timeout=25) as c:
    r=await c.post("https://api.mouser.com/api/v2/search/keyword",params={"apiKey":os.environ["MOUSER_API_KEY"]},json={"SearchByKeywordRequest":{"keyword":query,"records":limit,"startingRecord":0,"searchOptions":"","searchWithYourSignUpLanguage":""}});r.raise_for_status()
    for x in r.json().get("SearchResults",{}).get("Parts",[]):results.append({"provider":"Mouser","manufacturer":x.get("Manufacturer"),"mpn":x.get("ManufacturerPartNumber"),"description":x.get("Description"),"stock":x.get("Availability"),"price_breaks":x.get("PriceBreaks",[]),"datasheet":x.get("DataSheetUrl"),"verified_live":True})
  except Exception as e:providers["mouser_error"]=str(e)[:220]
 if providers["digikey"]:
  try:
   async with httpx.AsyncClient(timeout=25) as c:
    t=await c.post("https://api.digikey.com/v1/oauth2/token",data={"client_id":os.environ["DIGIKEY_CLIENT_ID"],"client_secret":os.environ["DIGIKEY_CLIENT_SECRET"],"grant_type":"client_credentials"});t.raise_for_status();token=t.json()["access_token"]
    r=await c.post("https://api.digikey.com/products/v4/search/keyword",headers={"Authorization":f"Bearer {token}","X-DIGIKEY-Client-Id":os.environ["DIGIKEY_CLIENT_ID"],"X-DIGIKEY-Locale-Site":"US","X-DIGIKEY-Locale-Language":"en","X-DIGIKEY-Locale-Currency":"USD","X-DIGIKEY-Locale-ShipTo":"US"},json={"Keywords":query,"Limit":limit});r.raise_for_status()
    for x in r.json().get("Products",[]):results.append({"provider":"DigiKey","manufacturer":x.get("Manufacturer",{}).get("Name"),"mpn":x.get("ManufacturerProductNumber"),"description":x.get("Description"),"stock":x.get("QuantityAvailable"),"datasheet":x.get("DatasheetUrl"),"product_url":x.get("ProductUrl"),"verified_live":True})
  except Exception as e:providers["digikey_error"]=str(e)[:220]
 return {"query":query,"results":results,"providers":providers,"lcsc_search_url":"https://www.lcsc.com/search?q="+query.replace(" ","%20"),"notice":"Only returned distributor records are live-verified. LCSC is a catalogue link until an authorised API/feed is configured."}
async def generate_product_visual(brief:str,design:dict)->bytes:
 token=os.getenv("REPLICATE_API_TOKEN")
 if not token:raise RuntimeError("Replicate image-generation credentials have not been configured. Add REPLICATE_API_TOKEN to the backend environment.")
 prompt=("Photorealistic industrial-design product concept render, studio product photography, neutral light grey background, three-quarter front view, premium manufacturable electronics hardware, realistic materials, subtle technical details, no text, no logo, no watermark. Concept render only, not verified CAD. Brief: "+brief+". Architecture: "+str([m.get("name") for m in design.get("modules",[])]))[:3500]
 async with httpx.AsyncClient(timeout=180) as c:
  if openai_key:
   r=await c.post("https://api.openai.com/v1/images/generations",headers={"Authorization":f"Bearer {openai_key}"},json={"model":"gpt-image-1","prompt":prompt,"size":"1536x1024","quality":"high","output_format":"png"});r.raise_for_status();encoded=r.json().get("data",[{}])[0].get("b64_json")
   if encoded:return base64.b64decode(encoded)
   raise RuntimeError("OpenAI image service returned no image data")
  r=await c.post("https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",headers={"Authorization":f"Bearer {token}","Prefer":"wait"},json={"input":{"prompt":prompt,"aspect_ratio":"4:3","output_format":"png","num_outputs":1}});r.raise_for_status();data=r.json()
  if data.get("status")!="succeeded":
   pid=data.get("id")
   for _ in range(18):
    import asyncio;await asyncio.sleep(5);q=await c.get("https://api.replicate.com/v1/predictions/"+pid,headers={"Authorization":f"Bearer {token}"});q.raise_for_status();data=q.json()
    if data.get("status") in ("succeeded","failed","canceled"):break
  if data.get("status")!="succeeded":raise RuntimeError("Image provider did not complete: "+str(data.get("error") or data.get("status")))
  output=data.get("output");url=output[0] if isinstance(output,list) else output
  if not url:raise RuntimeError("Image provider returned no image URL")
  image=await c.get(url);image.raise_for_status();return image.content
