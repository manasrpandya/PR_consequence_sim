export function duration(seconds:number):string{if(seconds<60)return `${seconds}s`;const minutes=Math.round(seconds/60);return minutes<60?`${minutes}m`:`${Math.floor(minutes/60)}h ${minutes%60}m`}
export function percent(value:number):string{return `${Math.round(value*100)}%`}
