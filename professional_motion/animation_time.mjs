/** A valid repeating curve parameter despite floating point boundary noise. */
export function loopPhase(value){
 if(!Number.isFinite(value))throw new RangeError('Finite animation time required');
 return ((value%1)+1)%1;
}
