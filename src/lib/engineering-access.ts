import {timingSafeEqual} from "node:crypto";
export function engineeringAccessError(supplied:string|null|undefined):"missing"|"invalid"|null{const expected=process.env.ENGINEERING_JOB_ACCESS_CODE;if(!expected)return "missing";const left=Buffer.from(supplied||"");const right=Buffer.from(expected);if(left.length!==right.length||!timingSafeEqual(left,right))return "invalid";return null;}
