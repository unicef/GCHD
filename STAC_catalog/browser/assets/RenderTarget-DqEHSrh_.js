import{B as L}from"./index-DXLj9f1R.js";import{bT as g,bU as c,cq as P,cr as $,cp as h,co as T,A as j,cv as M,d5 as N,I}from"./util-D3ZBeMIe.js";import{h as F,i as w,s as m,j as U,e as s,c as G,f as q,d as B,n as W,k as Z,l as H,g as D,G as J,F as Y}from"./compileUtil-DiOJJf7-.js";function V(){return{"fill-color":"rgba(255,255,255,0.4)","stroke-color":"#3399CC","stroke-width":1.25,"circle-radius":5,"circle-fill-color":"rgba(255,255,255,0.4)","circle-stroke-width":1.25,"circle-stroke-color":"#3399CC"}}const R=.985;function lt(t){return t-X(t)}function X(t){return Math.fround(t)}const K=`
vec2 df_from(float value) {
  return vec2(value, 0.);
}

float df_float(vec2 df) {
  return df.x;
}

vec2 df_add(vec2 dfa, vec2 dfb) {
  vec2 dfc;
  float t1, t2, e;
  
  t1 = dfa.x * u_one + dfb.x * u_one;
  e = t1 * u_one - dfa.x * u_one;
  t2 = ((dfb.x - e) + (dfa.x - (t1 - e))) * u_one + dfa.y + dfb.y * u_one;
  
  dfc.x = t1 * u_one + t2 * u_one;
  dfc.y = t2 - (dfc.x - t1) * u_one;
  return dfc;
}

vec2 df_sub(vec2 dfa, vec2 dfb) {
  vec2 dfc;
  float e, t1, t2;
  
  t1 = dfa.x - dfb.x;
  e = t1 - dfa.x;
  t2 = ((-dfb.x - e) + (dfa.x - (t1 - e))) + dfa.y - dfb.y;
  
  dfc.x = t1 + t2;
  dfc.y = t2 - (dfc.x - t1);
  return dfc;
}

vec2 df_mul(vec2 dfa, vec2 dfb) {
  vec2 dfc;
  float c11, c21, c2, e, t1, t2;
  float a1, a2, b1, b2, cona, conb, split = 4097.;

  cona = dfa.x * split * u_one;
  conb = dfb.x * split * u_one;
  a1 = cona * u_one - (cona - dfa.x);
  b1 = conb * u_one - (conb - dfb.x);
  a2 = dfa.x * u_one - a1;
  b2 = dfb.x * u_one - b1 * u_one;

  c11 = dfa.x * u_one * dfb.x * u_one;
  c21 = a2 * b2 * u_one + (a2 * b1 + (a1 * b2 + (a1 * b1 - c11))) * u_one;

  c2 = dfa.x * dfb.y * u_one + dfa.y * dfb.x * u_one;

  t1 = c11 + c2 * u_one;
  e = t1 - c11 * u_one;
  t2 = dfa.y * dfb.y * u_one + ((c2 - e) + (c11 - (t1 - e))) + c21 * u_one;

  dfc.x = t1 * u_one + t2 * u_one;
  dfc.y = t2 - (dfc.x - t1) * u_one;

  return dfc;
}

vec2 df_div(vec2 dfa, vec2 dfb) {
  vec2 dfc;
  float c11, c21, c2, e, t1, t2, t11, t12, t21, t22;
  float a1, a2, b1, b2, cona, conb, split = 4097.;
  float s1, s2;
  
  s1 = dfa.x / dfb.x * u_one;
  cona = s1 * split * u_one;
  conb = dfb.x * split * u_one;
  a1 = cona - (cona - s1) * u_one;
  b1 = conb - (conb - dfb.x) * u_one;
  a2 = s1 - a1 * u_one;
  b2 = dfb.x - b1 * u_one;
  
  c11 = s1 * dfb.x * u_one;
  c21 = (((a1 * b1 - c11) + a1 * b2) + a2 * b1) + a2 * b2 * u_one;
  
  c2 = s1 * dfb.y * u_one;
  
  t1 = c11 + c2 * u_one;
  e  = t1 - c11 * u_one;
  t2 = ((c2 - e) + (c11 - (t1 - e))) + c21 * u_one;
  
  t12 = t1 + t2 * u_one;
  t22 = t2 - (t12 - t1) * u_one;
  
  t11 = dfa.x - t12 * u_one;
  e   = t11 - dfa.x * u_one;
  t21 = ((-t12 - e) + (dfa.x - (t11 - e))) + dfa.y - t22 * u_one;
  
  s2 = (t11 + t21) / dfb.x * u_one;
  
  dfc.x = s1 + s2 * u_one;
  dfc.y = s2 - (dfc.x - s1) * u_one;
  
  return dfc;
}

float df_mod(vec2 df, vec2 m) {
  vec2 q = df_div(df, m) * u_one;
  float qf = floor(q.x);
  float frac = q.x - qf + q.y * u_one;
  if (frac < 0.0) qf -= 1.0;
  if (frac >= 1.0) qf += 1.0;
  vec2 prod = df_mul(df_from(qf), m);
  vec2 rem = df_add(df_from(df.x), df_from(-prod.x)) * u_one;
  rem.y += df.y - prod.y;
  return rem.x + rem.y * u_one;
}
`,E=`#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform float u_one;
uniform mat4 u_projectionMatrix;
uniform mat4 u_invertProjectionMatrix;
uniform vec2 u_viewportSizePx;
uniform float u_pixelRatio;
uniform float u_globalAlpha;
uniform float u_time;
uniform float u_zoom;
uniform float u_resolution;
uniform float u_rotation;
uniform vec4 u_renderExtent;
uniform float u_depth;
uniform mediump int u_hitDetection;

// these 64-bits floats are split into high/low
uniform vec2 u_df_patternOriginX;
uniform vec2 u_df_patternOriginY;
uniform vec2 u_df_patternScaleRatio;

const float PI = 3.141592653589793238;
const float TWO_PI = 2.0 * PI;
float currentLineMetric = 0.; // an actual value will be used in the stroke shaders

vec2 pxToWorld(vec2 pxPos) {
  vec2 screenPos = 2.0 * pxPos / u_viewportSizePx - 1.0;
  return (u_invertProjectionMatrix * vec4(screenPos, 0.0, 1.0)).xy;
}

vec2 worldToPx(vec2 worldPos) {
  vec4 screenPos = u_projectionMatrix * vec4(worldPos, 0.0, 1.0);
  return (0.5 * screenPos.xy + 0.5) * u_viewportSizePx;
}
${U}
${K}
`,b=V();class Q{constructor(){this.uniforms_=[],this.attributes_=[],this.hasSymbol_=!1,this.symbolSizeExpression_=`vec2(${F(b["circle-radius"])} + ${F(b["circle-stroke-width"]*.5)})`,this.symbolRotationExpression_="0.0",this.symbolOffsetExpression_="vec2(0.0)",this.symbolColorExpression_=w(b["circle-fill-color"]),this.texCoordExpression_="vec4(0.0, 0.0, 1.0, 1.0)",this.fragmentDiscardExpression_=null,this.shapeDiscardExpression_=null,this.symbolRotateWithView_=!1,this.hasStroke_=!1,this.strokeWidthExpression_=F(b["stroke-width"]),this.strokeColorExpression_=w(b["stroke-color"]),this.strokeOffsetExpression_="0.",this.strokeCapExpression_=m("round"),this.strokeJoinExpression_=m("round"),this.strokeMiterLimitExpression_="10.",this.strokeDistanceFieldExpression_="-1000.",this.strokePatternLengthExpression_=null,this.hasFill_=!1,this.fillColorExpression_=w(b["fill-color"]),this.fillPatternSizeExpression_=null,this.vertexShaderFunctions_=[],this.fragmentShaderFunctions_=[]}addUniform(e,o){return this.uniforms_.push({name:e,type:o}),this}addAttribute(e,o,n,i){return this.attributes_.push({name:e,type:o,varyingName:e.replace(/^a_/,"v_"),varyingType:i??o,varyingExpression:n??e}),this}setSymbolSizeExpression(e){return this.hasSymbol_=!0,this.symbolSizeExpression_=e,this}getSymbolSizeExpression(){return this.symbolSizeExpression_}setSymbolRotationExpression(e){return this.symbolRotationExpression_=e,this}setSymbolOffsetExpression(e){return this.symbolOffsetExpression_=e,this}getSymbolOffsetExpression(){return this.symbolOffsetExpression_}setSymbolColorExpression(e){return this.hasSymbol_=!0,this.symbolColorExpression_=e,this}getSymbolColorExpression(){return this.symbolColorExpression_}setTextureCoordinateExpression(e){return this.texCoordExpression_=e,this}setFragmentDiscardExpression(e){return this.fragmentDiscardExpression_=e,this}getFragmentDiscardExpression(){return this.fragmentDiscardExpression_}setShapeDiscardExpression(e){return this.shapeDiscardExpression_=e,this}getShapeDiscardExpression(){return this.shapeDiscardExpression_}setSymbolRotateWithView(e){return this.symbolRotateWithView_=e,this}setStrokeWidthExpression(e){return this.hasStroke_=!0,this.strokeWidthExpression_=e,this}setStrokeColorExpression(e){return this.hasStroke_=!0,this.strokeColorExpression_=e,this}getStrokeColorExpression(){return this.strokeColorExpression_}setStrokeOffsetExpression(e){return this.strokeOffsetExpression_=e,this}setStrokeCapExpression(e){return this.strokeCapExpression_=e,this}setStrokeJoinExpression(e){return this.strokeJoinExpression_=e,this}setStrokeMiterLimitExpression(e){return this.strokeMiterLimitExpression_=e,this}setStrokeDistanceFieldExpression(e){return this.strokeDistanceFieldExpression_=e,this}setStrokePatternLengthExpression(e){return this.strokePatternLengthExpression_=e,this}getStrokePatternLengthExpression(){return this.strokePatternLengthExpression_}setFillColorExpression(e){return this.hasFill_=!0,this.fillColorExpression_=e,this}getFillColorExpression(){return this.fillColorExpression_}setFillPatternSizeExpression(e){return this.fillPatternSizeExpression_=e,this}getFillPatternSizeExpression(){return this.fillPatternSizeExpression_}addVertexShaderFunction(e){return this.vertexShaderFunctions_.includes(e)?this:(this.vertexShaderFunctions_.push(e),this)}addFragmentShaderFunction(e){return this.fragmentShaderFunctions_.includes(e)?this:(this.fragmentShaderFunctions_.push(e),this)}getSymbolVertexShader(){return this.hasSymbol_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
attribute vec2 a_position;
attribute vec2 a_localPosition;
attribute vec2 a_hitColor;

varying vec2 v_texCoord;
varying vec2 v_quadCoord;
varying vec4 v_hitColor;
varying vec2 v_centerPx;
varying float v_angle;
varying vec2 v_quadSizePx;

${this.attributes_.map(e=>`attribute ${e.type} ${e.name};
varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.vertexShaderFunctions_.join(`
`)}
vec2 pxToScreen(vec2 coordPx) {
  vec2 scaled = coordPx / u_viewportSizePx / 0.5;
  return scaled;
}

vec2 screenToPx(vec2 coordScreen) {
  return (coordScreen * 0.5 + 0.5) * u_viewportSizePx;
}

void main(void) {
  v_quadSizePx = ${this.symbolSizeExpression_};
  vec2 halfSizePx = v_quadSizePx * 0.5;
  vec2 centerOffsetPx = ${this.symbolOffsetExpression_};
  vec2 offsetPx = centerOffsetPx + a_localPosition * halfSizePx * vec2(1., -1.);
  float angle = ${this.symbolRotationExpression_}${this.symbolRotateWithView_?" + u_rotation":""};
  float c = cos(-angle);
  float s = sin(-angle);
  offsetPx = vec2(c * offsetPx.x - s * offsetPx.y, s * offsetPx.x + c * offsetPx.y);
  vec4 center = u_projectionMatrix * vec4(a_position, 0.0, 1.0);
  gl_Position = center + vec4(pxToScreen(offsetPx), u_depth, 0.);
  vec4 texCoord = ${this.texCoordExpression_};
  float u = mix(texCoord.s, texCoord.p, a_localPosition.x * 0.5 + 0.5);
  float v = mix(texCoord.t, texCoord.q, a_localPosition.y * 0.5 + 0.5);
  v_texCoord = vec2(u, v);
  v_hitColor = unpackColor(a_hitColor);
  v_angle = angle;
  c = cos(-v_angle);
  s = sin(-v_angle);
  centerOffsetPx = vec2(c * centerOffsetPx.x - s * centerOffsetPx.y, s * centerOffsetPx.x + c * centerOffsetPx.y);
  v_centerPx = screenToPx(center.xy) + centerOffsetPx;
${this.attributes_.map(e=>`  ${e.varyingName} = ${e.varyingExpression};`).join(`
`)}
${this.shapeDiscardExpression_?`  if (${this.shapeDiscardExpression_}) { gl_Position = vec4(2.0, 2.0, 0.0, 0.0); }`:""}
}`:null}getSymbolFragmentShader(){return this.hasSymbol_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
varying vec2 v_texCoord;
varying vec4 v_hitColor;
varying vec2 v_centerPx;
varying float v_angle;
varying vec2 v_quadSizePx;
${this.attributes_.map(e=>`varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.fragmentShaderFunctions_.join(`
`)}

void main(void) {
${this.attributes_.map(e=>`  ${e.varyingType} ${e.name} = ${e.varyingName}; // assign to original attribute name`).join(`
`)}
${this.fragmentDiscardExpression_?`  if (${this.fragmentDiscardExpression_}) { discard; }`:""}
  vec2 coordsPx = gl_FragCoord.xy / u_pixelRatio - v_centerPx; // relative to center
  float c = cos(v_angle);
  float s = sin(v_angle);
  coordsPx = vec2(c * coordsPx.x - s * coordsPx.y, s * coordsPx.x + c * coordsPx.y);
  gl_FragColor = ${this.symbolColorExpression_};
  gl_FragColor.rgb *= gl_FragColor.a;
  if (u_hitDetection > 0) {
    if (gl_FragColor.a < 0.05) { discard; };
    gl_FragColor = v_hitColor;
  }
}`:null}getStrokeVertexShader(){return this.hasStroke_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
attribute vec2 a_segmentStart;
attribute vec2 a_segmentEnd;
attribute vec2 a_localPosition;
attribute float a_measureStart;
attribute float a_measureEnd;
attribute float a_angleTangentSum;
attribute float a_distanceLow;
attribute float a_distanceHigh;
attribute vec2 a_joinAngles;
attribute vec2 a_hitColor;

varying vec2 v_segmentStartPx;
varying vec2 v_segmentEndPx;
varying float v_angleStart;
varying float v_angleEnd;
varying float v_width;
varying vec4 v_hitColor;
varying float v_distancePx;
varying float v_measureStart;
varying float v_measureEnd;

${this.attributes_.map(e=>`attribute ${e.type} ${e.name};
varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.vertexShaderFunctions_.join(`
`)}

vec4 pxToScreen(vec2 pxPos) {
  vec2 screenPos = 2.0 * pxPos / u_viewportSizePx - 1.0;
  return vec4(screenPos, u_depth, 1.0);
}

bool isCap(float joinAngle) {
  return joinAngle < -0.1;
}

vec2 getJoinOffsetDirection(vec2 normalPx, float joinAngle) {
  float halfAngle = joinAngle / 2.0;
  float c = cos(halfAngle);
  float s = sin(halfAngle);
  vec2 angleBisectorNormal = vec2(s * normalPx.x + c * normalPx.y, -c * normalPx.x + s * normalPx.y);
  float length = 1.0 / s;
  return angleBisectorNormal * length;
}

vec2 getOffsetPoint(vec2 point, vec2 normal, float joinAngle, float offsetPx) {
  // if on a cap or the join angle is too high, offset the line along the segment normal
  if (cos(joinAngle) > 0.998 || isCap(joinAngle)) {
    return point - normal * offsetPx;
  }
  // offset is applied along the inverted normal (positive offset goes "right" relative to line direction)
  return point - getJoinOffsetDirection(normal, joinAngle) * offsetPx;
}

void main(void) {
  v_angleStart = a_joinAngles.x;
  v_angleEnd = a_joinAngles.y;
  float startEndRatio = a_localPosition.x * 0.5 + 0.5;
  currentLineMetric = mix(a_measureStart, a_measureEnd, startEndRatio);
  // we're reading the fractional part while keeping the sign (so -4.12 gives -0.12, 3.45 gives 0.45)

  float lineWidth = ${this.strokeWidthExpression_};
  float lineOffsetPx = ${this.strokeOffsetExpression_};

  // compute segment start/end in px with offset
  vec2 segmentStartPx = worldToPx(a_segmentStart);
  vec2 segmentEndPx = worldToPx(a_segmentEnd);
  vec2 tangentPx = normalize(segmentEndPx - segmentStartPx);
  vec2 normalPx = vec2(-tangentPx.y, tangentPx.x);
  segmentStartPx = getOffsetPoint(segmentStartPx, normalPx, v_angleStart, lineOffsetPx),
  segmentEndPx = getOffsetPoint(segmentEndPx, normalPx, v_angleEnd, lineOffsetPx);

  // compute current vertex position
  float normalDir = -1. * a_localPosition.y;
  float tangentDir = -1. * a_localPosition.x;
  float angle = mix(v_angleStart, v_angleEnd, startEndRatio);
  vec2 joinDirection;
  vec2 positionPx = mix(segmentStartPx, segmentEndPx, startEndRatio);
  // if angle is too high, do not make a proper join
  if (cos(angle) > ${R} || isCap(angle)) {
    joinDirection = normalPx * normalDir - tangentPx * tangentDir;
  } else {
    joinDirection = getJoinOffsetDirection(normalPx * normalDir, angle);
  }
  positionPx = positionPx + joinDirection * (lineWidth * 0.5 + 1.); // adding 1 pixel for antialiasing
  gl_Position = pxToScreen(positionPx);

  v_segmentStartPx = segmentStartPx;
  v_segmentEndPx = segmentEndPx;
  v_width = lineWidth;
  v_hitColor = unpackColor(a_hitColor);

  v_distancePx = a_distanceLow / u_resolution - (lineOffsetPx * a_angleTangentSum);
  float distanceHighPx = a_distanceHigh / u_resolution;
  ${this.strokePatternLengthExpression_!==null?`v_distancePx = mod(v_distancePx, ${this.strokePatternLengthExpression_});
  distanceHighPx = mod(distanceHighPx, ${this.strokePatternLengthExpression_});
  `:""}v_distancePx += distanceHighPx;

  v_measureStart = a_measureStart;
  v_measureEnd = a_measureEnd;
${this.attributes_.map(e=>`  ${e.varyingName} = ${e.varyingExpression};`).join(`
`)}
${this.shapeDiscardExpression_?`  if (${this.shapeDiscardExpression_}) { gl_Position = vec4(2.0, 2.0, 0.0, 0.0); }`:""}
}`:null}getStrokeFragmentShader(){return this.hasStroke_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
varying vec2 v_segmentStartPx;
varying vec2 v_segmentEndPx;
varying float v_angleStart;
varying float v_angleEnd;
varying float v_width;
varying vec4 v_hitColor;
varying float v_distancePx;
varying float v_measureStart;
varying float v_measureEnd;
${this.attributes_.map(e=>`varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.fragmentShaderFunctions_.join(`
`)}

bool isCap(float joinAngle) {
  return joinAngle < -0.1;
}

float segmentDistanceField(vec2 point, vec2 start, vec2 end, float width) {
  vec2 tangent = normalize(end - start);
  vec2 normal = vec2(-tangent.y, tangent.x);
  vec2 startToPoint = point - start;
  return abs(dot(startToPoint, normal)) - width * 0.5;
}

float buttCapDistanceField(vec2 point, vec2 start, vec2 end) {
  vec2 startToPoint = point - start;
  vec2 tangent = normalize(end - start);
  return dot(startToPoint, -tangent);
}

float squareCapDistanceField(vec2 point, vec2 start, vec2 end, float width) {
  return buttCapDistanceField(point, start, end) - width * 0.5;
}

float roundCapDistanceField(vec2 point, vec2 start, vec2 end, float width) {
  float onSegment = max(0., 1000. * dot(point - start, end - start)); // this is very high when inside the segment
  return length(point - start) - width * 0.5 - onSegment;
}

float roundJoinDistanceField(vec2 point, vec2 start, vec2 end, float width) {
  return roundCapDistanceField(point, start, end, width);
}

float bevelJoinField(vec2 point, vec2 start, vec2 end, float width, float joinAngle) {
  vec2 startToPoint = point - start;
  vec2 tangent = normalize(end - start);
  float c = cos(joinAngle * 0.5);
  float s = sin(joinAngle * 0.5);
  float direction = -sign(sin(joinAngle));
  vec2 bisector = vec2(c * tangent.x - s * tangent.y, s * tangent.x + c * tangent.y);
  float radius = width * 0.5 * s;
  return dot(startToPoint, bisector * direction) - radius;
}

float miterJoinDistanceField(vec2 point, vec2 start, vec2 end, float width, float joinAngle) {
  if (cos(joinAngle) > ${R}) { // avoid risking a division by zero
    return bevelJoinField(point, start, end, width, joinAngle);
  }
  float miterLength = 1. / sin(joinAngle * 0.5);
  float miterLimit = ${this.strokeMiterLimitExpression_};
  if (miterLength > miterLimit) {
    return bevelJoinField(point, start, end, width, joinAngle);
  }
  return -1000.;
}

float capDistanceField(vec2 point, vec2 start, vec2 end, float width, float capType) {
   if (capType == ${m("butt")}) {
    return buttCapDistanceField(point, start, end);
  } else if (capType == ${m("square")}) {
    return squareCapDistanceField(point, start, end, width);
  }
  return roundCapDistanceField(point, start, end, width);
}

float joinDistanceField(vec2 point, vec2 start, vec2 end, float width, float joinAngle, float joinType) {
  if (joinType == ${m("bevel")}) {
    return bevelJoinField(point, start, end, width, joinAngle);
  } else if (joinType == ${m("miter")}) {
    return miterJoinDistanceField(point, start, end, width, joinAngle);
  }
  return roundJoinDistanceField(point, start, end, width);
}

float computeSegmentPointDistance(vec2 point, vec2 start, vec2 end, float width, float joinAngle, float capType, float joinType) {
  if (isCap(joinAngle)) {
    return capDistanceField(point, start, end, width, capType);
  }
  return joinDistanceField(point, start, end, width, joinAngle, joinType);
}

float distanceFromSegment(vec2 point, vec2 start, vec2 end) {
  vec2 tangent = end - start;
  vec2 startToPoint = point - start;
  // inspire by capsule fn in https://iquilezles.org/articles/distfunctions/
  float h = clamp(dot(startToPoint, tangent) / dot(tangent, tangent), 0.0, 1.0);
  return length(startToPoint - tangent * h);
}

void main(void) {
${this.attributes_.map(e=>`  ${e.varyingType} ${e.name} = ${e.varyingName}; // assign to original attribute name`).join(`
`)}

  vec2 currentPointPx = gl_FragCoord.xy / u_pixelRatio;
  vec2 worldPos = pxToWorld(currentPointPx);
  if (
    abs(u_renderExtent[0] - u_renderExtent[2]) > 0.0 && (
      worldPos[0] < u_renderExtent[0] ||
      worldPos[1] < u_renderExtent[1] ||
      worldPos[0] > u_renderExtent[2] ||
      worldPos[1] > u_renderExtent[3]
    )
  ) {
    discard;
  }

  float segmentLengthPx = length(v_segmentEndPx - v_segmentStartPx);
  segmentLengthPx = max(segmentLengthPx, 1.17549429e-38); // avoid divide by zero
  vec2 segmentTangent = (v_segmentEndPx - v_segmentStartPx) / segmentLengthPx;
  vec2 segmentNormal = vec2(-segmentTangent.y, segmentTangent.x);
  vec2 startToPointPx = currentPointPx - v_segmentStartPx;
  float lengthToPointPx = max(0., min(dot(segmentTangent, startToPointPx), segmentLengthPx));
  float currentLengthPx = lengthToPointPx + v_distancePx;
  float currentRadiusPx = distanceFromSegment(currentPointPx, v_segmentStartPx, v_segmentEndPx);
  float currentRadiusRatio = dot(segmentNormal, startToPointPx) * 2. / v_width;
  currentLineMetric = mix(v_measureStart, v_measureEnd, lengthToPointPx / segmentLengthPx);

${this.fragmentDiscardExpression_?`  if (${this.fragmentDiscardExpression_}) { discard; }`:""}

  float capType = ${this.strokeCapExpression_};
  float joinType = ${this.strokeJoinExpression_};
  float segmentStartDistance = computeSegmentPointDistance(currentPointPx, v_segmentStartPx, v_segmentEndPx, v_width, v_angleStart, capType, joinType);
  float segmentEndDistance = computeSegmentPointDistance(currentPointPx, v_segmentEndPx, v_segmentStartPx, v_width, v_angleEnd, capType, joinType);
  float distanceField = max(
    segmentDistanceField(currentPointPx, v_segmentStartPx, v_segmentEndPx, v_width),
    max(segmentStartDistance, segmentEndDistance)
  );
  distanceField = max(distanceField, ${this.strokeDistanceFieldExpression_});

  vec4 color = ${this.strokeColorExpression_};
  color.a *= smoothstep(0.5, -0.5, distanceField);
  gl_FragColor = color;
  gl_FragColor.a *= u_globalAlpha;
  gl_FragColor.rgb *= gl_FragColor.a;
  if (u_hitDetection > 0) {
    if (gl_FragColor.a < 0.1) { discard; };
    gl_FragColor = v_hitColor;
  }
}`:null}getFillVertexShader(){return this.hasFill_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
attribute vec2 a_position;
attribute vec2 a_hitColor;

varying vec4 v_hitColor;
varying vec2 v_patternOriginPx;
varying vec2 v_patternSizePx;

${this.attributes_.map(e=>`attribute ${e.type} ${e.name};
varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.vertexShaderFunctions_.join(`
`)}
void main(void) {
  gl_Position = u_projectionMatrix * vec4(a_position, u_depth, 1.0);
  v_hitColor = unpackColor(a_hitColor);
${this.fillPatternSizeExpression_!==null?`
  // this computes the pattern offset in screenspace using double-float arithmetics
  v_patternSizePx = ${this.fillPatternSizeExpression_};
  vec2 patternSizeScaledX = df_mul(df_from(v_patternSizePx.x), u_df_patternScaleRatio);
  vec2 patternSizeScaledY = df_mul(df_from(v_patternSizePx.y), u_df_patternScaleRatio);
  v_patternOriginPx = vec2(
    df_mod(u_df_patternOriginX, patternSizeScaledX),
    df_mod(u_df_patternOriginY, patternSizeScaledY)
  );

  // reapply rotation to the pattern origin
  v_patternOriginPx -= u_viewportSizePx / 2.; // translate to viewport center
  v_patternOriginPx = vec2(
    cos(-u_rotation) * v_patternOriginPx.x - sin(-u_rotation) * v_patternOriginPx.y,
    sin(-u_rotation) * v_patternOriginPx.x + cos(-u_rotation) * v_patternOriginPx.y
  );
  v_patternOriginPx += u_viewportSizePx / 2.; // translate back
`:"  v_patternOriginPx = vec2(0.);"}
${this.attributes_.map(e=>`  ${e.varyingName} = ${e.varyingExpression};`).join(`
`)}
${this.shapeDiscardExpression_?`  if (${this.shapeDiscardExpression_}) { gl_Position = vec4(2.0, 2.0, 0.0, 0.0); }`:""}
}`:null}getFillFragmentShader(){return this.hasFill_?`${E}
${this.uniforms_.map(e=>`uniform ${e.type} ${e.name};`).join(`
`)}
varying vec4 v_hitColor;
varying vec2 v_patternOriginPx;
varying vec2 v_patternSizePx;
${this.attributes_.map(e=>`varying ${e.varyingType} ${e.varyingName};`).join(`
`)}
${this.fragmentShaderFunctions_.join(`
`)}

void main(void) {
${this.attributes_.map(e=>`  ${e.varyingType} ${e.name} = ${e.varyingName}; // assign to original attribute name`).join(`
`)}
  vec2 pxPos = gl_FragCoord.xy / u_pixelRatio;
  vec2 worldPos = pxToWorld(pxPos);
  if (
    abs(u_renderExtent[0] - u_renderExtent[2]) > 0.0 && (
      worldPos[0] < u_renderExtent[0] ||
      worldPos[1] < u_renderExtent[1] ||
      worldPos[0] > u_renderExtent[2] ||
      worldPos[1] > u_renderExtent[3]
    )
  ) {
    discard;
  }
${this.fragmentDiscardExpression_?`  if (${this.fragmentDiscardExpression_}) { discard; }`:""}
  gl_FragColor = ${this.fillColorExpression_};
  gl_FragColor.a *= u_globalAlpha;
  gl_FragColor.rgb *= gl_FragColor.a;
  if (u_hitDetection > 0) {
    if (gl_FragColor.a < 0.1) { discard; };
    gl_FragColor = v_hitColor;
  }
}`:null}}function ft(){const t='const t=new Set;let e=!1;function n(e,n,i=2){const f=n&&n.length,u=f?n[0]*i:e.length;t.size&&t.clear();let s=r(e,0,u,i,!0);const v=[];if(!s||s.next===s.prev)return v;let b=0,A=0,m=0;if(f&&(s=function(e,n,x,i){const f=[];for(let o=0,x=n.length;o<x;o++){const u=r(e,n[o]*i,o<x-1?n[o+1]*i:e.length,i,!1);u===u.next&&t.add(u),f.push(B(u))}f.sort(l),function(t,e){const n=Math.ceil((t+2*e)/y)+e+2;h.length<4*n&&(h=new Float64Array(4*n));p=0}(e.length/i,n.length),M(x,x),c=!0;for(let t=0;t<f.length;t++)x=a(f[t],x);return c=!1,o(x)}(e,n,s,i)),e.length>80*i){b=e[0],A=e[1];let t=b,n=A;for(let r=i;r<u;r+=i){const o=e[r],x=e[r+1];o<b&&(b=o),x<A&&(A=x),o>t&&(t=o),x>n&&(n=x)}m=Math.max(t-b,n-A),m=0!==m?32767/m:0}return x(s,v,b,A,m),v}function r(t,e,n,r,o){let x=null;if(o===function(t,e,n,r){let o=0;for(let x=e,i=n-r;x<n;x+=r)o+=(t[i]-t[x])*(t[x+1]+t[i+1]),i=x;return o}(t,e,n,r)>0)for(let o=e;o<n;o+=r)x=G(o/r|0,t[o],t[o+1],x);else for(let o=n-r;o>=e;o-=r)x=G(o/r|0,t[o],t[o+1],x);return x&&N(x,x.next)&&(k(x),x=x.next),x}function o(n,r=n){const o=r===n;let x,i=n;do{x=!1,i===i.next||0!==t.size&&t.has(i)||!N(i,i.next)&&0!==S(i.prev,i,i.next)?(o||i!==r)&&(i=i.next,x=!o):((o||i===r)&&(r=i.prev),e=!0,k(i),i=i.prev,x=!0)}while(x||i!==r);return r}function x(t,n,r,x,c){c&&function(t,e,n,r){let o=t,x=0;do{o.z=I(o.x,o.y,e,n,r),w[x++]=o,o=o.next}while(o!==t);!function(t){if(t<=32){for(let e=1;e<t;e++){const t=w[e],n=t.z;let r=e-1;for(;r>=0&&w[r].z>n;)w[r+1]=w[r],r--;w[r+1]=t}return}F.length<t&&(F=new Uint32Array(t),Z=new Uint32Array(t),d=new Array(t));for(let e=0;e<t;e++)F[e]=w[e].z;E(t,w,F,d,Z,0),E(t,d,Z,w,F,8),E(t,w,F,d,Z,16),E(t,d,Z,w,F,24)}(x);let i=null;for(let t=0;t<x;t++){const e=w[t];e.prevZ=i,i&&(i.nextZ=e),i=e}i.nextZ=null}(t,r,x,c);let l=t,a=!1;for(;t.prev!==t.next;){const y=t.prev,h=t.next;if(S(y,t,h)<0&&(c?f(t,r,x,c):i(t)))n.push(y.i,t.i,h.i),k(t),t=h,l=h;else if((t=h)===l){if(e=!1,t=o(t),e){l=t;continue}if(!a){l=t=u(t,n),a=!0;continue}s(t,n,r,x,c);break}}}function i(t){const e=t.prev,n=t,r=t.next,o=e.x,x=n.x,i=r.x,f=e.y,u=n.y,s=r.y,c=Math.min(o,x,i),l=Math.min(f,u,s),a=Math.max(o,x,i),y=Math.max(f,u,s);let h=r.next;for(;h!==e;){if(h.x>=c&&h.x<=a&&h.y>=l&&h.y<=y&&(o!==h.x||f!==h.y)&&U(o,f,x,u,i,s,h.x,h.y)&&S(h.prev,h,h.next)>=0)return!1;h=h.next}return!0}function f(t,e,n,r){const o=t.prev,x=t,i=t.next,f=o.x,u=x.x,s=i.x,c=o.y,l=x.y,a=i.y,y=Math.min(f,u,s),h=Math.min(c,l,a),p=Math.max(f,u,s),v=Math.max(c,l,a),b=I(y,h,e,n,r),M=I(p,v,e,n,r);let A=t.prevZ;for(;A&&A.z>=b;){if(A.x>=y&&A.x<=p&&A.y>=h&&A.y<=v&&A!==i&&(f!==A.x||c!==A.y)&&U(f,c,u,l,s,a,A.x,A.y)&&S(A.prev,A,A.next)>=0)return!1;A=A.prevZ}let m=t.nextZ;for(;m&&m.z<=M;){if(m.x>=y&&m.x<=p&&m.y>=h&&m.y<=v&&m!==i&&(f!==m.x||c!==m.y)&&U(f,c,u,l,s,a,m.x,m.y)&&S(m.prev,m,m.next)>=0)return!1;m=m.nextZ}return!0}function u(t,e){let n=t,r=!1;do{const o=n.prev,x=n.next.next;R(o,n,n.next,x,!1)&&_(o,x)&&_(x,o)&&(e.push(o.i,n.i,x.i),k(n),k(n.next),n=t=x,r=!0),n=n.next}while(n!==t);return r?o(n):n}function s(t,e,n,r,i){let f=t;do{let t=f.next.next;for(;t!==f.prev;){if(f.i!==t.i&&P(f,t)){let u=O(f,t);return f=o(f,f.next),u=o(u,u.next),x(f,e,n,r,i),void x(u,e,n,r,i)}t=t.next}f=f.next}while(f!==t)}let c=!1;function l(t,e){return t.x-e.x||t.y-e.y||(t.next.y-t.y)/(t.next.x-t.x)-(e.next.y-e.y)/(e.next.x-e.x)}function a(t,e){const n=function(t,e){let n=e;const r=t.x,o=t.y;let x,i=-1/0;if(N(t,n))return n;for(let e=0,f=0;e<p;e++,f+=4){if(o<h[f+1]||o>h[f+3]||h[f]>r||h[f+2]<=i)continue;const u=A(e);n=m(e);do{if(n.prev.next===n){if(N(t,n.next))return n.next;if(o<=n.y&&o>=n.next.y&&n.next.y!==n.y){const t=n.x+(o-n.y)*(n.next.x-n.x)/(n.next.y-n.y);if(t<=r&&t>i&&(i=t,x=n.x<n.next.x?n:n.next,t===r))return x}}n=n.next}while(n!==u)}if(!x)return null;const f=x.x,u=x.y,s=Math.min(o,u),c=Math.max(o,u);let l=1/0;for(let e=0,a=0;e<p;e++,a+=4){if(h[a+2]<f||h[a]>r||h[a+3]<s||h[a+1]>c)continue;const y=A(e);n=m(e);do{if(n.prev.next===n&&r>=n.x&&n.x>=f&&r!==n.x&&U(o<u?r:i,o,f,u,o<u?i:r,o,n.x,n.y)){const e=Math.abs(o-n.y)/(r-n.x);(_(n,t)||n.y===o&&n.next.y===o&&n.next.x>r)&&(e<l||e===l&&(n.x>x.x||n.x===x.x&&g(x,n)))&&(x=n,l=e)}n=n.next}while(n!==y)}return x}(t,e);if(!n)return e;const r=O(n,t);return M(n,r.next.next),o(r,r.next),o(n,n.next)}const y=16;let h=new Float64Array(0),p=0;const v=[],b=[];function M(t,e){let n=t;do{const t=p++;v[t]=n;let r=1/0,o=1/0,x=-1/0,i=-1/0,f=0;do{const e=n.next;n.z=t,n.x<r&&(r=n.x),n.x>x&&(x=n.x),n.y<o&&(o=n.y),n.y>i&&(i=n.y),e.x<r&&(r=e.x),e.x>x&&(x=e.x),e.y<o&&(o=e.y),e.y>i&&(i=e.y),n=e}while(++f<y&&n!==e);b[t]=n;const u=4*t;h[u]=r,h[u+1]=o,h[u+2]=x,h[u+3]=i}while(n!==e)}function A(t){let e=b[t];for(;e.prev.next!==e;)e=e.next;return b[t]=e,e}function m(t){let e=v[t];for(;e.prev.next!==e;)e=e.next;return v[t]=e,e}function g(t,e){return S(t.prev,t,e.prev)<0&&S(e.next,t,t.next)<0}const w=[];let d=[],F=new Uint32Array(0),Z=new Uint32Array(0);const z=new Uint32Array(256);function E(t,e,n,r,o,x){z.fill(0);for(let e=0;e<t;e++)z[n[e]>>>x&255]++;let i=0;for(let t=0;t<256;t++){const e=z[t];z[t]=i,i+=e}for(let i=0;i<t;i++){const t=n[i],f=z[t>>>x&255]++;r[f]=e[i],o[f]=t}}function I(t,e,n,r,o){return(t=1431655765&((t=858993459&((t=252645135&((t=16711935&((t=(t-n)*o|0)|t<<8))|t<<4))|t<<2))|t<<1))|(e=1431655765&((e=858993459&((e=252645135&((e=16711935&((e=(e-r)*o|0)|e<<8))|e<<4))|e<<2))|e<<1))<<1}function B(t){let e=t,n=t;do{(e.x<n.x||e.x===n.x&&e.y<n.y)&&(n=e),e=e.next}while(e!==t);return n}function U(t,e,n,r,o,x,i,f){return(o-i)*(e-f)>=(t-i)*(x-f)&&(t-i)*(r-f)>=(n-i)*(e-f)&&(n-i)*(x-f)>=(o-i)*(r-f)}function P(t,e){const n=N(t,e)&&S(t.prev,t,t.next)>0&&S(e.prev,e,e.next)>0;return t.next.i!==e.i&&(n||_(t,e)&&_(e,t)&&(0!==S(t.prev,t,e.prev)||0!==S(t,e.prev,e)))&&!function(t,e){const n=Math.min(t.x,e.x),r=Math.max(t.x,e.x),o=Math.min(t.y,e.y),x=Math.max(t.y,e.y);let i=t;do{const f=i.next;if(i.x>r&&f.x>r||i.x<n&&f.x<n||i.y>x&&f.y>x||i.y<o&&f.y<o)i=f;else{if(i.i!==t.i&&f.i!==t.i&&i.i!==e.i&&f.i!==e.i&&R(i,f,t,e))return!0;i=f}}while(i!==t);return!1}(t,e)&&(n||function(t,e){let n=t,r=!1;const o=(t.x+e.x)/2,x=(t.y+e.y)/2;do{const t=n.next;n.y>x!=t.y>x&&o<(t.x-n.x)*(x-n.y)/(t.y-n.y)+n.x&&(r=!r),n=t}while(n!==t);return r}(t,e))}function S(t,e,n){return(e.y-t.y)*(n.x-e.x)-(e.x-t.x)*(n.y-e.y)}function N(t,e){return t.x===e.x&&t.y===e.y}function R(t,e,n,r,o=!0){const x=S(t,e,n),i=S(t,e,r),f=S(n,r,t),u=S(n,r,e);return(x>0&&i<0||x<0&&i>0)&&(f>0&&u<0||f<0&&u>0)||!!o&&(!(0!==x||!T(t,n,e))||(!(0!==i||!T(t,r,e))||(!(0!==f||!T(n,t,r))||!(0!==u||!T(n,e,r)))))}function T(t,e,n){return e.x<=Math.max(t.x,n.x)&&e.x>=Math.min(t.x,n.x)&&e.y<=Math.max(t.y,n.y)&&e.y>=Math.min(t.y,n.y)}function _(t,e){return S(t.prev,t,t.next)<0?S(t,e,t.next)>=0&&S(t,t.prev,e)>=0:S(t,e,t.prev)<0||S(t,t.next,e)<0}function O(t,e){const n=j(t.i,t.x,t.y),r=j(e.i,e.x,e.y),o=t.next,x=e.prev;return t.next=e,e.prev=t,n.next=o,o.prev=n,r.next=n,n.prev=r,x.next=r,r.prev=x,r}function G(t,e,n,r){const o=j(t,e,n);return r?(o.next=r.next,o.prev=r,r.next.prev=o,r.next=o):(o.prev=o,o.next=o),o}function k(t){t.next.prev=t.prev,t.prev.next=t.next,t.prevZ&&(t.prevZ.nextZ=t.nextZ),t.nextZ&&(t.nextZ.prevZ=t.prevZ),c&&function(t,e){const n=4*t.z;e.x<h[n]&&(h[n]=e.x),e.y<h[n+1]&&(h[n+1]=e.y),e.x>h[n+2]&&(h[n+2]=e.x),e.y>h[n+3]&&(h[n+3]=e.y)}(t.prev,t.next)}function j(t,e,n){return{i:t,x:e,y:n,prev:null,next:null,z:0,prevZ:null,nextZ:null}}function q(t,e,n){const r=Math.sqrt((e[0]-t[0])*(e[0]-t[0])+(e[1]-t[1])*(e[1]-t[1])),o=[(e[0]-t[0])/r,(e[1]-t[1])/r],x=[-o[1],o[0]],i=Math.sqrt((n[0]-t[0])*(n[0]-t[0])+(n[1]-t[1])*(n[1]-t[1])),f=[(n[0]-t[0])/i,(n[1]-t[1])/i];let u=0===r||0===i?0:Math.acos((s=f[0]*o[0]+f[1]*o[1],c=-1,l=1,Math.min(Math.max(s,c),l)));var s,c,l;u=Math.max(u,1e-5);return f[0]*x[0]+f[1]*x[1]>0?u:2*Math.PI-u}const L=[1,0,0,1,0,0];function Y(t,e){const n=e[0],r=e[1];return e[0]=t[0]*n+t[2]*r+t[4],e[1]=t[1]*n+t[3]*r+t[5],e}function C(t,e){const n=(r=e)[0]*r[3]-r[1]*r[2];var r;!function(t,e){if(!t)throw new Error(e)}(0!==n,"Transformation matrix cannot be inverted");const o=e[0],x=e[1],i=e[2],f=e[3],u=e[4],s=e[5];return t[0]=f/n,t[1]=-x/n,t[2]=-i/n,t[3]=o/n,t[4]=(i*s-f*u)/n,t[5]=-(o*s-x*u)/n,t}new Array(6);const D=[],H={vertexAttributesPosition:0,instanceAttributesPosition:0,indicesPosition:0};function J(t,e,n,r,o){const x=t[e++],i=t[e++],f=D;f.length=r;for(let n=0;n<f.length;n++)f[n]=t[e+n];let u=o?o.instanceAttributesPosition:0;return n[u++]=x,n[u++]=i,f.length&&(n.set(f,u),u+=f.length),H.instanceAttributesPosition=u,H}function K(t,e,n,r,o,x,i,f,u,s){const c=[t[e],t[e+1]],l=[t[n],t[n+1]],a=t[e+2],y=t[n+2],h=Y(f,[...c]),p=Y(f,[...l]);let v=-1,b=-1,M=s;const A=null!==o;if(null!==r){v=q(h,p,Y(f,[...[t[r],t[r+1]]])),Math.cos(v)<=.985&&(M+=Math.tan((v-Math.PI)/2))}if(A){b=q(p,h,Y(f,[...[t[o],t[o+1]]])),Math.cos(b)<=.985&&(M+=Math.tan((Math.PI-b)/2))}const m=Math.pow(2,24),g=u%m,w=Math.floor(u/m)*m;return x.push(c[0],c[1],a,l[0],l[1],y,v,b,g,w,s),x.push(...i),{length:u+Math.sqrt((p[0]-h[0])*(p[0]-h[0])+(p[1]-h[1])*(p[1]-h[1])),angle:M}}function Q(t,e,r,o,x){const i=2+x;let f=e;const u=t.slice(f,f+x);f+=x;const s=t[f++];let c=0;const l=new Array(s-1);for(let e=0;e<s;e++)c+=t[f++],e<s-1&&(l[e]=c);const a=t.slice(f,f+2*c),y=n(a,l,2);for(let t=0;t<y.length;t++)o.push(y[t]+r.length/i);for(let t=0;t<a.length;t+=2)r.push(a[t],a[t+1],...u);return f+2*c}const V="GENERATE_POLYGON_BUFFERS",W="GENERATE_POINT_BUFFERS",X="GENERATE_LINE_STRING_BUFFERS",$=self;$.onmessage=t=>{const e=t.data;switch(e.type){case W:{const t=2,n=2,r=e.customAttributesSize,o=n+r,x=new Float32Array(e.renderInstructions),i=x.length/o*(t+r),f=Uint32Array.from([0,1,3,1,2,3]),u=Float32Array.from([-1,-1,1,-1,1,1,-1,1]),s=new Float32Array(i);let c;for(let t=0;t<x.length;t+=o)c=J(x,t,s,r,c);const l=Object.assign({indicesBuffer:f.buffer,vertexAttributesBuffer:u.buffer,instanceAttributesBuffer:s.buffer,renderInstructions:x.buffer},e);$.postMessage(l,[u.buffer,s.buffer,f.buffer,x.buffer]);break}case X:{const t=[],n=e.customAttributesSize,r=3,o=new Float32Array(e.renderInstructions);let x=0;const i=e.renderInstructionsTransform,f=L.slice(0);let u,s;for(C(f,i);x<o.length;){s=Array.from(o.slice(x,x+n)),x+=n,u=o[x++];const e=x,i=x+(u-1)*r,c=o[e]===o[i]&&o[e+1]===o[i+1];let l=0,a=0;for(let n=0;n<u-1;n++){let y=null;n>0?y=x+(n-1)*r:c&&(y=i-r);let h=null;n<u-2?h=x+(n+2)*r:c&&(h=e+r);const p=K(o,x+n*r,x+(n+1)*r,y,h,t,s,f,l,a);l=p.length,a=p.angle}x+=u*r}const c=Uint32Array.from([0,1,3,1,2,3]),l=Float32Array.from([-1,-1,1,-1,1,1,-1,1]),a=Float32Array.from(t),y=Object.assign({indicesBuffer:c.buffer,vertexAttributesBuffer:l.buffer,instanceAttributesBuffer:a.buffer,renderInstructions:o.buffer},e);$.postMessage(y,[l.buffer,a.buffer,c.buffer,o.buffer]);break}case V:{const t=[],n=[],r=e.customAttributesSize,o=new Float32Array(e.renderInstructions);let x=0;for(;x<o.length;)x=Q(o,x,t,n,r);const i=Uint32Array.from(n),f=Float32Array.from(t),u=Float32Array.from([]),s=Object.assign({indicesBuffer:i.buffer,vertexAttributesBuffer:f.buffer,instanceAttributesBuffer:u.buffer,renderInstructions:o.buffer},e);$.postMessage(s,[f.buffer,u.buffer,i.buffer,o.buffer]);break}}};';return new Worker(typeof Blob>"u"?"data:application/javascript;base64,"+L.from(t,"binary").toString("base64"):URL.createObjectURL(new Blob([t],{type:"application/javascript"})))}const xt={GENERATE_POLYGON_BUFFERS:"GENERATE_POLYGON_BUFFERS",GENERATE_POINT_BUFFERS:"GENERATE_POINT_BUFFERS",GENERATE_LINE_STRING_BUFFERS:"GENERATE_LINE_STRING_BUFFERS"},ut={BUILD_INSTRUCTIONS:"BUILD_INSTRUCTIONS",DISPOSE_INSTRUCTIONS:"DISPOSE_INSTRUCTIONS",RENDER:"RENDER"};function dt(t,e){e=e||[];const o=256,n=o-1,i=Math.floor(t/o/o/o)/n,r=Math.floor(t/o/o)%o/n,x=Math.floor(t/o)%o/n,f=t%o/n;return e[0]=i*256*255+r*255,e[1]=x*256*255+f*255,e}function pt(t){let e=0;const o=256,n=o-1;return e+=Math.round(t[0]*o*o*o*n),e+=Math.round(t[1]*o*o*n),e+=Math.round(t[2]*o*n),e+=Math.round(t[3]*n),e}function k(t){return(JSON.stringify(t).split("").reduce((o,n)=>(o<<5)-o+n.charCodeAt(0),0)>>>0).toString()}function C(t,e,o,n){if(`${n}radius`in t&&n!=="icon-"){let i=s(o,t[`${n}radius`],c);if(`${n}radius2`in t){const r=s(o,t[`${n}radius2`],c);i=`max(${i}, ${r})`}`${n}stroke-width`in t&&(i=`(${i} + ${s(o,t[`${n}stroke-width`],c)} * 0.5)`),e.setSymbolSizeExpression(`vec2(${i} * 2. + 0.5)`)}if(`${n}scale`in t){const i=s(o,t[`${n}scale`],$);e.setSymbolSizeExpression(`${e.getSymbolSizeExpression()} * ${i}`)}`${n}displacement`in t&&e.setSymbolOffsetExpression(s(o,t[`${n}displacement`],P)),`${n}rotation`in t&&e.setSymbolRotationExpression(s(o,t[`${n}rotation`],c)),`${n}rotate-with-view`in t&&e.setSymbolRotateWithView(!!t[`${n}rotate-with-view`])}function O(t,e,o,n,i){let r="vec4(0.)";if(e!==null&&(r=e),o!==null&&n!==null){const a=`smoothstep(-${n} + 0.63, -${n} - 0.58, ${t})`;r=`mix(${o}, ${r}, ${a})`}const x=`(1.0 - smoothstep(-0.63, 0.58, ${t}))`;let f=`${r} * vec4(1.0, 1.0, 1.0, ${x})`;return i!==null&&(f=`${f} * vec4(1.0, 1.0, 1.0, ${i})`),f}function A(t,e,o,n,i){const r=new Image;r.crossOrigin=t[`${n}cross-origin`]===void 0?"anonymous":t[`${n}cross-origin`],j(typeof t[`${n}src`]=="string",`WebGL layers do not support expressions for the ${n}src style property`),r.src=t[`${n}src`],o[`u_texture${i}_size`]=()=>r.complete?[r.width,r.height]:[0,0],e.addUniform(`u_texture${i}_size`,"vec2");const x=`u_texture${i}_size`;return o[`u_texture${i}`]=r,e.addUniform(`u_texture${i}`,"sampler2D"),x}function z(t,e,o,n,i){let r=s(o,t[`${e}offset`],$);if(`${e}offset-origin`in t)switch(t[`${e}offset-origin`]){case"top-right":r=`vec2(${n}.x, 0.) + ${i} * vec2(-1., 0.) + ${r} * vec2(-1., 1.)`;break;case"bottom-left":r=`vec2(0., ${n}.y) + ${i} * vec2(0., -1.) + ${r} * vec2(1., -1.)`;break;case"bottom-right":r=`${n} - ${i} - ${r}`;break}return r}function tt(t,e,o,n){n.functions.circleDistanceField=`float circleDistanceField(vec2 point, float radius) {
  return length(point) - radius;
}`,C(t,e,n,"circle-");let i=null;"circle-opacity"in t&&(i=s(n,t["circle-opacity"],c));let r="coordsPx";"circle-scale"in t&&(r=`coordsPx / ${s(n,t["circle-scale"],$)}`);let x=null;"circle-fill-color"in t&&(x=s(n,t["circle-fill-color"],g));let f=null;"circle-stroke-color"in t&&(f=s(n,t["circle-stroke-color"],g));let a=s(n,t["circle-radius"],c),l=null;"circle-stroke-width"in t&&(l=s(n,t["circle-stroke-width"],c),a=`(${a} + ${l} * 0.5)`);const u=`circleDistanceField(${r}, ${a})`,p=O(u,x,f,l,i);e.setSymbolColorExpression(p)}function et(t,e,o,n){n.functions.round=`float round(float v) {
  return sign(v) * floor(abs(v) + 0.5);
}`,n.functions.starDistanceField=`float starDistanceField(vec2 point, float numPoints, float radius, float radius2, float angle) {
  float startAngle = -PI * 0.5 + angle; // tip starts upwards and rotates clockwise with angle
  float c = cos(startAngle);
  float s = sin(startAngle);
  vec2 pointRotated = vec2(c * point.x - s * point.y, s * point.x + c * point.y);
  float alpha = TWO_PI / numPoints; // the angle of one sector
  float beta = atan(pointRotated.y, pointRotated.x);
  float gamma = round(beta / alpha) * alpha; // angle in sector
  c = cos(-gamma);
  s = sin(-gamma);
  vec2 inSector = vec2(c * pointRotated.x - s * pointRotated.y, abs(s * pointRotated.x + c * pointRotated.y));
  vec2 tipToPoint = inSector + vec2(-radius, 0.);
  vec2 edgeNormal = vec2(radius2 * sin(alpha * 0.5), -radius2 * cos(alpha * 0.5) + radius);
  return dot(normalize(edgeNormal), tipToPoint);
}`,n.functions.regularDistanceField=`float regularDistanceField(vec2 point, float numPoints, float radius, float angle) {
  float startAngle = -PI * 0.5 + angle; // tip starts upwards and rotates clockwise with angle
  float c = cos(startAngle);
  float s = sin(startAngle);
  vec2 pointRotated = vec2(c * point.x - s * point.y, s * point.x + c * point.y);
  float alpha = TWO_PI / numPoints; // the angle of one sector
  float radiusIn = radius * cos(PI / numPoints);
  float beta = atan(pointRotated.y, pointRotated.x);
  float gamma = round((beta - alpha * 0.5) / alpha) * alpha + alpha * 0.5; // angle in sector from mid
  c = cos(-gamma);
  s = sin(-gamma);
  vec2 inSector = vec2(c * pointRotated.x - s * pointRotated.y, abs(s * pointRotated.x + c * pointRotated.y));
  return inSector.x - radiusIn;
}`,C(t,e,n,"shape-");let i=null;"shape-opacity"in t&&(i=s(n,t["shape-opacity"],c));let r="coordsPx";"shape-scale"in t&&(r=`coordsPx / ${s(n,t["shape-scale"],$)}`);let x=null;"shape-fill-color"in t&&(x=s(n,t["shape-fill-color"],g));let f=null;"shape-stroke-color"in t&&(f=s(n,t["shape-stroke-color"],g));let a=null;"shape-stroke-width"in t&&(a=s(n,t["shape-stroke-width"],c));const l=s(n,t["shape-points"],c);let u="0.";"shape-angle"in t&&(u=s(n,t["shape-angle"],c));let p,_=s(n,t["shape-radius"],c);if(a!==null&&(_=`${_} + ${a} * 0.5`),"shape-radius2"in t){let d=s(n,t["shape-radius2"],c);a!==null&&(d=`${d} + ${a} * 0.5`),p=`starDistanceField(${r}, ${l}, ${_}, ${d}, ${u})`}else p=`regularDistanceField(${r}, ${l}, ${_}, ${u})`;const S=O(p,x,f,a,i);e.setSymbolColorExpression(S)}function nt(t,e,o,n){let i="vec4(1.0)";"icon-color"in t&&(i=s(n,t["icon-color"],g)),"icon-opacity"in t&&(i=`${i} * vec4(1.0, 1.0, 1.0, ${s(n,t["icon-opacity"],c)})`);const r=k(t["icon-src"]),x=A(t,e,o,"icon-",r);if(e.setSymbolColorExpression(`${i} * texture2D(u_texture${r}, v_texCoord)`).setSymbolSizeExpression(x),"icon-width"in t&&"icon-height"in t&&e.setSymbolSizeExpression(`vec2(${s(n,t["icon-width"],c)}, ${s(n,t["icon-height"],c)})`),"icon-offset"in t&&"icon-size"in t){const f=s(n,t["icon-size"],P),a=e.getSymbolSizeExpression();e.setSymbolSizeExpression(f);const l=z(t,"icon-",n,"v_quadSizePx",f);e.setTextureCoordinateExpression(`(vec4((${l}).xyxy) + vec4(0., 0., ${f})) / (${a}).xyxy`)}if(C(t,e,n,"icon-"),"icon-anchor"in t){const f=s(n,t["icon-anchor"],P);let a="1.0";"icon-scale"in t&&(a=s(n,t["icon-scale"],$));let l;t["icon-anchor-x-units"]==="pixels"&&t["icon-anchor-y-units"]==="pixels"?l=`${f} * ${a}`:t["icon-anchor-x-units"]==="pixels"?l=`${f} * vec2(vec2(${a}).x, v_quadSizePx.y)`:t["icon-anchor-y-units"]==="pixels"?l=`${f} * vec2(v_quadSizePx.x, vec2(${a}).x)`:l=`${f} * v_quadSizePx`;let u=`v_quadSizePx * vec2(0.5, -0.5) + ${l} * vec2(-1., 1.)`;if("icon-anchor-origin"in t)switch(t["icon-anchor-origin"]){case"top-right":u=`v_quadSizePx * -0.5 + ${l}`;break;case"bottom-left":u=`v_quadSizePx * 0.5 - ${l}`;break;case"bottom-right":u=`v_quadSizePx * vec2(-0.5, 0.5) + ${l} * vec2(1., -1.)`;break}e.setSymbolOffsetExpression(`${e.getSymbolOffsetExpression()} + ${u}`)}}function it(t,e,o,n){if("stroke-color"in t&&e.setStrokeColorExpression(s(n,t["stroke-color"],g)),"stroke-pattern-src"in t){const i=k(t["stroke-pattern-src"]),r=A(t,e,o,"stroke-pattern-",i);let x=r,f="vec2(0.)";"stroke-pattern-offset"in t&&"stroke-pattern-size"in t&&(x=s(n,t["stroke-pattern-size"],P),f=z(t,"stroke-pattern-",n,r,x));let a="0.";"stroke-pattern-spacing"in t&&(a=s(n,t["stroke-pattern-spacing"],c));let l="0.";"stroke-pattern-start-offset"in t&&(l=s(n,t["stroke-pattern-start-offset"],c)),n.functions.sampleStrokePattern=`vec4 sampleStrokePattern(sampler2D texture, vec2 textureSize, vec2 textureOffset, vec2 sampleSize, float spacingPx, float startOffsetPx, float currentLengthPx, float currentRadiusRatio, float lineWidth) {
  float currentLengthScaled = (currentLengthPx - startOffsetPx) * sampleSize.y / lineWidth;
  float spacingScaled = spacingPx * sampleSize.y / lineWidth;
  float uCoordPx = mod(currentLengthScaled, (sampleSize.x + spacingScaled));
  float isInsideOfPattern = step(uCoordPx, sampleSize.x);
  float vCoordPx = (-currentRadiusRatio * 0.5 + 0.5) * sampleSize.y;
  // make sure that we're not sampling too close to the borders to avoid interpolation with outside pixels
  uCoordPx = clamp(uCoordPx, 0.5, sampleSize.x - 0.5);
  vCoordPx = clamp(vCoordPx, 0.5, sampleSize.y - 0.5);
  vec2 texCoord = (vec2(uCoordPx, vCoordPx) + textureOffset) / textureSize;
  return texture2D(texture, texCoord) * vec4(1.0, 1.0, 1.0, isInsideOfPattern);
}`;const u=`u_texture${i}`;let p="1.";"stroke-color"in t&&(p=e.getStrokeColorExpression()),e.setStrokeColorExpression(`${p} * sampleStrokePattern(${u}, ${r}, ${f}, ${x}, ${a}, ${l}, currentLengthPx, currentRadiusRatio, v_width)`),n.functions.computeStrokePatternLength=`float computeStrokePatternLength(vec2 sampleSize, float spacingPx, float lineWidth) {
  float patternLengthPx = sampleSize.x / sampleSize.y * lineWidth;
  return patternLengthPx + spacingPx;
}`,e.setStrokePatternLengthExpression(`computeStrokePatternLength(${x}, ${a}, v_width)`)}if("stroke-width"in t&&e.setStrokeWidthExpression(s(n,t["stroke-width"],c)),"stroke-offset"in t&&e.setStrokeOffsetExpression(s(n,t["stroke-offset"],c)),"stroke-line-cap"in t&&e.setStrokeCapExpression(s(n,t["stroke-line-cap"],h)),"stroke-line-join"in t&&e.setStrokeJoinExpression(s(n,t["stroke-line-join"],h)),"stroke-miter-limit"in t&&e.setStrokeMiterLimitExpression(s(n,t["stroke-miter-limit"],c)),"stroke-line-dash"in t){n.functions.getSingleDashDistance=`float getSingleDashDistance(float distance, float radius, float dashOffset, float dashLength, float dashLengthTotal, float capType, float lineWidth) {
  float localDistance = mod(distance, dashLengthTotal);
  float distanceSegment = abs(localDistance - dashOffset - dashLength * 0.5) - dashLength * 0.5;
  distanceSegment = min(distanceSegment, dashLengthTotal - localDistance);
  if (capType == ${m("square")}) {
    distanceSegment -= lineWidth * 0.5;
  } else if (capType == ${m("round")}) {
    distanceSegment = min(distanceSegment, sqrt(distanceSegment * distanceSegment + radius * radius) - lineWidth * 0.5);
  }
  return distanceSegment;
}`;let i=t["stroke-line-dash"].map(d=>s(n,d,c));i.length%2===1&&(i=[...i,...i]);let r="0.";"stroke-line-dash-offset"in t&&(r=s(n,t["stroke-line-dash-offset"],c));const f=`dashDistanceField_${k(t["stroke-line-dash"])}`,a=i.map((d,y)=>`float dashLength${y}`).join(", "),l=i.map((d,y)=>`dashLength${y}`).join(" + ");let u="0.",p=`getSingleDashDistance(distance, radius, ${u}, dashLength0, totalDashLength, capType, lineWidth)`;for(let d=2;d<i.length;d+=2)u=`${u} + dashLength${d-2} + dashLength${d-1}`,p=`min(${p}, getSingleDashDistance(distance, radius, ${u}, dashLength${d}, totalDashLength, capType, lineWidth))`;n.functions[f]=`float ${f}(float distance, float radius, float capType, float lineWidth, ${a}) {
  float totalDashLength = ${l};
  return ${p};
}`;const _=i.map((d,y)=>`${d}`).join(", ");e.setStrokeDistanceFieldExpression(`${f}(currentLengthPx + ${r}, currentRadiusPx, capType, v_width, ${_})`);let S=i.join(" + ");e.getStrokePatternLengthExpression()&&(n.functions.combinePatternLengths=`float combinePatternLengths(float patternLength1, float patternLength2) {
  return patternLength1 * patternLength2;
}`,S=`combinePatternLengths(${e.getStrokePatternLengthExpression()}, ${S})`),e.setStrokePatternLengthExpression(S)}}function ot(t,e,o,n){if("fill-color"in t&&e.setFillColorExpression(s(n,t["fill-color"],g)),"fill-pattern-src"in t){const i=k(t["fill-pattern-src"]),r=A(t,e,o,"fill-pattern-",i);e.setFillPatternSizeExpression(r);let x="vec2(0.)";if("fill-pattern-offset"in t&&"fill-pattern-size"in t){const l=s(n,t["fill-pattern-size"],P);e.setFillPatternSizeExpression(l),x=z(t,"fill-pattern-",n,r,"v_patternSizePx")}n.functions.sampleFillPattern=`vec4 sampleFillPattern(sampler2D texture, vec2 textureSize, vec2 textureOffset, vec2 sampleSize, vec2 patternOriginPx, vec2 pxPosition, float sampleScaleRatio) {
  vec2 pxRelativePos = pxPosition - patternOriginPx;

  // rotate the relative position from origin by the current view rotation
  pxRelativePos = vec2(pxRelativePos.x * cos(u_rotation) - pxRelativePos.y * sin(u_rotation), pxRelativePos.x * sin(u_rotation) + pxRelativePos.y * cos(u_rotation));
  // sample position is computed according to the sample offset & size
  vec2 samplePos = mod(pxRelativePos / sampleScaleRatio, sampleSize);
  // also make sure that we're not sampling too close to the borders to avoid interpolation with outside pixels
  samplePos = clamp(samplePos, vec2(0.5), sampleSize - vec2(0.5));
  samplePos.y = sampleSize.y - samplePos.y; // invert y axis so that images appear upright
  return texture2D(texture, (samplePos + textureOffset) / textureSize);
}`;const f=`u_texture${i}`;let a="1.";"fill-color"in t&&(a=e.getFillColorExpression()),e.setFillColorExpression(`${a} * sampleFillPattern(${f}, ${r}, ${x}, v_patternSizePx, v_patternOriginPx, pxPos, df_float(u_df_patternScaleRatio))`)}}function rt(t,e,o,n){function i(...r){try{s(...r)}catch{}}"text-value"in t&&i(n,t["text-value"],h),"text-font"in t&&i(n,t["text-font"],h),"text-max-angle"in t&&i(n,t["text-max-angle"],c),"text-offset-x"in t&&i(n,t["text-offset-x"],c),"text-offset-y"in t&&i(n,t["text-offset-y"],c),"text-overflow"in t&&i(n,t["text-overflow"],T),"text-placement"in t&&i(n,t["text-placement"],h),"text-repeat"in t&&i(n,t["text-repeat"],c),"text-scale"in t&&i(n,t["text-scale"],$),"text-rotate-with-view"in t&&i(n,t["text-rotate-with-view"],T),"text-rotation"in t&&i(n,t["text-rotation"],c),"text-align"in t&&i(n,t["text-align"],h),"text-justify"in t&&i(n,t["text-justify"],h),"text-baseline"in t&&i(n,t["text-baseline"],h),"text-padding"in t&&i(n,t["text-padding"],P),"text-fill-color"in t&&i(n,t["text-fill-color"],g),"text-stroke-color"in t&&i(n,t["text-stroke-color"],g),"text-stroke-line-cap"in t&&i(n,t["text-stroke-line-cap"],h),"text-stroke-line-join"in t&&i(n,t["text-stroke-line-join"],h),"text-stroke-line-dash"in t&&i(n,t["text-stroke-line-dash"],P),"text-stroke-line-dash-offset"in t&&i(n,t["text-stroke-line-dash-offset"],c),"text-stroke-miter-limit"in t&&i(n,t["text-stroke-miter-limit"],c),"text-stroke-width"in t&&i(n,t["text-stroke-width"],c),"text-background-fill-color"in t&&i(n,t["text-background-fill-color"],g),"text-background-stroke-color"in t&&i(n,t["text-background-stroke-color"],g),"text-background-stroke-line-cap"in t&&i(n,t["text-background-stroke-line-cap"],h),"text-background-stroke-line-join"in t&&i(n,t["text-background-stroke-line-join"],h),"text-background-stroke-line-dash"in t&&i(n,t["text-background-stroke-line-dash"],P),"text-background-stroke-line-dash-offset"in t&&i(n,t["text-background-stroke-line-dash-offset"],c),"text-background-stroke-miter-limit"in t&&i(n,t["text-background-stroke-miter-limit"],c),"text-background-stroke-width"in t&&i(n,t["text-background-stroke-width"],c),"z-index"in t&&i(n,t["z-index"],c)}function ht(t,e,o){const n=W(e),i=new Q,r={};if("icon-src"in t?nt(t,i,r,n):"shape-points"in t?et(t,i,r,n):"circle-radius"in t&&tt(t,i,r,n),it(t,i,r,n),ot(t,i,r,n),rt(t,i,r,n),o){const a=M(e),l=s(n,o,T,a);a.mCoordinate?i.setFragmentDiscardExpression(`!${l}`):i.setShapeDiscardExpression(`!${l}`)}const x={};function f(a,l,u,p){if(!n[a])return;const _=Z(u),S=H(u);i.addAttribute(`a_${l}`,_),x[l]={size:S,callback:p}}return f("geometryType",J,h,a=>D(N(a.getGeometry()))),f("featureId",Y,h|c,a=>{const l=a.getId()??null;return typeof l=="string"?D(l):l}),G(i,n),{builder:i,attributes:{...x,...B(n)},uniforms:{...r,...q(n,e)}}}const v=new Uint8Array(4);class gt{constructor(e,o){this.helper_=e;const n=e.getGL();this.texture_=n.createTexture(),this.framebuffer_=n.createFramebuffer(),this.depthbuffer_=n.createRenderbuffer(),this.size_=o||[1,1],this.data_=new Uint8Array(0),this.dataCacheDirty_=!0,this.updateSize_()}setSize(e){I(e,this.size_)||(this.size_[0]=e[0],this.size_[1]=e[1],this.updateSize_())}getSize(){return this.size_}clearCachedData(){this.dataCacheDirty_=!0}readAll(){if(this.dataCacheDirty_){const e=this.size_,o=this.helper_.getGL();o.bindFramebuffer(o.FRAMEBUFFER,this.framebuffer_),o.readPixels(0,0,e[0],e[1],o.RGBA,o.UNSIGNED_BYTE,this.data_),this.dataCacheDirty_=!1}return this.data_}readPixel(e,o){if(e<0||o<0||e>this.size_[0]||o>=this.size_[1])return v[0]=0,v[1]=0,v[2]=0,v[3]=0,v;this.readAll();const n=Math.floor(e)+(this.size_[1]-Math.floor(o)-1)*this.size_[0];return v[0]=this.data_[n*4],v[1]=this.data_[n*4+1],v[2]=this.data_[n*4+2],v[3]=this.data_[n*4+3],v}getTexture(){return this.texture_}getFramebuffer(){return this.framebuffer_}getDepthbuffer(){return this.depthbuffer_}updateSize_(){const e=this.size_,o=this.helper_.getGL();this.texture_=this.helper_.createTexture(e,null,this.texture_),o.bindFramebuffer(o.FRAMEBUFFER,this.framebuffer_),o.viewport(0,0,e[0],e[1]),o.framebufferTexture2D(o.FRAMEBUFFER,o.COLOR_ATTACHMENT0,o.TEXTURE_2D,this.texture_,0),o.bindRenderbuffer(o.RENDERBUFFER,this.depthbuffer_),o.renderbufferStorage(o.RENDERBUFFER,o.DEPTH_COMPONENT16,e[0],e[1]),o.framebufferRenderbuffer(o.FRAMEBUFFER,o.DEPTH_ATTACHMENT,o.RENDERBUFFER,this.depthbuffer_),this.data_=new Uint8Array(e[0]*e[1]*4)}}export{Q as S,ut as T,gt as W,dt as a,ft as b,pt as c,xt as d,lt as e,X as g,ht as p};
//# sourceMappingURL=RenderTarget-DqEHSrh_.js.map
