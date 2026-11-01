import {NextRequest, NextResponse} from "next/server";

export const runtime = "nodejs";
export const maxDuration = 30;

type Part = {provider:"Mouser"|"DigiKey";manufacturer:string;manufacturer_part_number:string;distributor_part_number:string;description:string;availability:string|null;datasheet_url:string|null;product_url:string|null;image_url:string|null;lifecycle:string|null;price_breaks:Array<{quantity:number|null;unit_price:string|null;currency:string|null}>};
let digikeyToken:{value:string;expiresAt:number}|null=null;
const text=(v:unknown):string=>typeof v==="string"||typeof v==="number"?String(v):"";
const safeUrl=(v:unknown):string|null=>{if(typeof v!=="string"||!v)return null;try{const u=new URL(v);return u.protocol==="https:"?u.toString():null;}catch{return null;}};
const asArray=(v:unknown):Record<string,unknown>[]=>Array.isArray(v)?v.filter((x):x is Record<string,unknown>=>Boolean(x)&&typeof x==="object"):[];
async function searchMouser(query:string):Promise<Part[]>{
 const key=process.env.MOUSER_API_KEY;if(!key)return [];
 const res=await fetch("https://api.mouser.com/api/v2/search/keyword?apiKey="+encodeURIComponent(key),{method:"POST",headers:{"Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify({SearchByKeywordRequest:{keyword:query,records:10,startingRecord:0,searchOptions:"",searchWithYourSignUpLanguage:""}}),signal:AbortSignal.timeout(12000)});
 if(!res.ok)throw new Error("Mouser API returned HTTP "+res.status);
 const data=await res.json() as {SearchResults?:{Parts?:unknown[]}};
 return asArray(data.SearchResults?.Parts).map(p=>({provider:"Mouser",manufacturer:text(p.Manufacturer),manufacturer_part_number:text(p.ManufacturerPartNumber),distributor_part_number:text(p.MouserPartNumber),description:text(p.Description),availability:text(p.Availability)||null,datasheet_url:safeUrl(p.DataSheetUrl),product_url:safeUrl(p.ProductDetailUrl),image_url:safeUrl(p.ImagePath),lifecycle:text(p.LifecycleStatus)||null,price_breaks:asArray(p.PriceBreaks).map(b=>({quantity:Number(b.Quantity)||null,unit_price:text(b.Price)||null,currency:text(b.Currency)||null}))}));
}
async function getDigiKeyToken():Promise<string>{
 if(digikeyToken&&digikeyToken.expiresAt>Date.now()+30000)return digikeyToken.value;
 const id=process.env.DIGIKEY_CLIENT_ID,secret=process.env.DIGIKEY_CLIENT_SECRET;if(!id||!secret)throw new Error("DigiKey credentials are not configured");
 const res=await fetch("https://api.digikey.com/v1/oauth2/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({client_id:id,client_secret:secret,grant_type:"client_credentials"}),signal:AbortSignal.timeout(10000)});
 if(!res.ok)throw new Error("DigiKey OAuth returned HTTP "+res.status);
 const data=await res.json() as {access_token?:string;expires_in?:number};if(!data.access_token)throw new Error("DigiKey OAuth returned no access token");
 digikeyToken={value:data.access_token,expiresAt:Date.now()+Math.max(60,data.expires_in||600)*1000};return data.access_token;
}
async function searchDigiKey(query:string):Promise<Part[]>{
 const id=process.env.DIGIKEY_CLIENT_ID;if(!id||!process.env.DIGIKEY_CLIENT_SECRET)return [];
 const token=await getDigiKeyToken();
 const res=await fetch("https://api.digikey.com/products/v4/search/keyword",{method:"POST",headers:{"Authorization":"Bearer "+token,"X-DIGIKEY-Client-Id":id,"X-DIGIKEY-Locale-Site":"US","X-DIGIKEY-Locale-Language":"en","X-DIGIKEY-Locale-Currency":"USD","Content-Type":"application/json","Accept":"application/json"},body:JSON.stringify({Keywords:query,Limit:10}),signal:AbortSignal.timeout(12000)});
 if(!res.ok)throw new Error("DigiKey Product API returned HTTP "+res.status);
 const data=await res.json() as {Products?:unknown[]};
 return asArray(data.Products).map(p=>({provider:"DigiKey",manufacturer:text((p.Manufacturer as Record<string,unknown>|undefined)?.Name),manufacturer_part_number:text(p.ManufacturerProductNumber),distributor_part_number:text(p.DigiKeyProductNumber),description:text(p.ProductDescription),availability:text(p.QuantityAvailable)||null,datasheet_url:safeUrl(p.DatasheetUrl),product_url:safeUrl(p.ProductUrl),image_url:safeUrl(p.PhotoUrl),lifecycle:text(p.ProductStatus)||null,price_breaks:[]}));
}
export async function POST(req:NextRequest){try{
 const body=await req.json() as {query?:unknown};const query=typeof body.query==="string"?body.query.trim():"";
 if(query.length<2||query.length>160)return NextResponse.json({detail:"Search query must contain 2–160 characters."},{status:422});
 const providers=[{name:"Mouser",configured:Boolean(process.env.MOUSER_API_KEY),run:()=>searchMouser(query)},{name:"DigiKey",configured:Boolean(process.env.DIGIKEY_CLIENT_ID&&process.env.DIGIKEY_CLIENT_SECRET),run:()=>searchDigiKey(query)}];
 const active=providers.filter(p=>p.configured);if(!active.length)return NextResponse.json({detail:"No component supplier credentials are configured. Add MOUSER_API_KEY or DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET.",providers:providers.map(({name,configured})=>({name,configured})),results:[]},{status:503});
 const settled=await Promise.allSettled(active.map(p=>p.run()));const results:Part[]=[];
 const providerStatus=providers.map(p=>{const i=active.findIndex(a=>a.name===p.name);if(i<0)return{name:p.name,configured:false,status:"not_configured"};const result=settled[i];if(result.status==="fulfilled"){results.push(...result.value);return{name:p.name,configured:true,status:"connected",result_count:result.value.length};}return{name:p.name,configured:true,status:"error",message:result.reason instanceof Error?result.reason.message:"Supplier request failed"};});
 return NextResponse.json({query,results,providers:providerStatus,result_count:results.length,warning:"Supplier availability and pricing are live vendor data and must be rechecked before purchase. Search results are not engineering approval."},{headers:{"Cache-Control":"no-store"}});
 }catch(error){return NextResponse.json({detail:error instanceof Error?error.message:"Supplier search failed."},{status:400});}}
