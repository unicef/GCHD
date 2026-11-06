import{bS as v,br as R,bT as b,bU as _}from"./util-D3ZBeMIe.js";import{W as $,e as g,U as r,P as x,A as m,n as C,u as y,g as I}from"./compileUtil-DiOJJf7-.js";import N from"./BaseTile-Dh0PjFht.js";import"./utils-BFUSjNrH.js";import"./_commonjsHelpers-CE1G-McA.js";import"./GeoJSON-CwvOf9Jd.js";import"./index-GX9wAUec.js";import"./I18N-BC6F-L_M.js";import"./BFormRadioGroup.vue_vue_type_script_setup_true_lang-DaMHx4U3-BiL54gp1.js";import"./useStateClass-BGbSLWFN-BDF2_qKX.js";import"./ConditionalWrapper.vue_vue_type_script_lang-IX_NpHH--BwbeIDa1.js";import"./mat4-CZmcDzWz.js";import"./DataTile-BF3wLxY2.js";import"./Tile-Dah-_ulY.js";import"./Tile-CcIDT1g7.js";import"./common-D4No0chS.js";import"./TileRange-2Tc-Ry00.js";import"./LRUCache-CvQMkFfe.js";import"./tilecoord-CB41OhTn.js";import"./TileProperty-BF4LcWSy.js";function L(a,e,t){const s=`
    attribute vec2 ${m.TEXTURE_COORD};
    uniform mat4 ${r.TILE_TRANSFORM};
    uniform float ${r.TEXTURE_PIXEL_WIDTH};
    uniform float ${r.TEXTURE_PIXEL_HEIGHT};
    uniform float ${r.TEXTURE_RESOLUTION};
    uniform float ${r.DEPTH};

    varying vec2 v_textureCoord;
    varying vec2 v_localMapCoord;

    void main() {
      v_textureCoord = ${m.TEXTURE_COORD};
      v_localMapCoord = vec2(
        ${r.TEXTURE_PIXEL_WIDTH} * ${r.TEXTURE_RESOLUTION} * v_textureCoord[0],
        -1. * ${r.TEXTURE_PIXEL_HEIGHT} * ${r.TEXTURE_RESOLUTION} * v_textureCoord[1]
      );
      gl_Position = ${r.TILE_TRANSFORM} * vec4(${m.TEXTURE_COORD}, ${r.DEPTH}, 1.0);
    }
  `,o={...C(),bandCount:e},i=[];if(a.color!==void 0){const n=g(o,a.color,b);i.push(`color = ${n};`)}if(a.contrast!==void 0){const n=g(o,a.contrast,_);i.push(`color.rgb = clamp((${n} + 1.0) * color.rgb - (${n} / 2.0), vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 1.0));`)}if(a.exposure!==void 0){const n=g(o,a.exposure,_);i.push(`color.rgb = clamp((${n} + 1.0) * color.rgb, vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 1.0));`)}if(a.saturation!==void 0){const n=g(o,a.saturation,_);i.push(`
      float saturation = ${n} + 1.0;
      float sr = (1.0 - saturation) * 0.2126;
      float sg = (1.0 - saturation) * 0.7152;
      float sb = (1.0 - saturation) * 0.0722;
      mat3 saturationMatrix = mat3(
        sr + saturation, sr, sr,
        sg, sg + saturation, sg,
        sb, sb, sb + saturation
      );
      color.rgb = clamp(saturationMatrix * color.rgb, vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 1.0));
    `)}if(a.gamma!==void 0){const n=g(o,a.gamma,_);i.push(`color.rgb = pow(color.rgb, vec3(1.0 / ${n}));`)}if(a.brightness!==void 0){const n=g(o,a.brightness,_);i.push(`color.rgb = clamp(color.rgb + ${n}, vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 1.0));`)}const c={};if(o.variables.size>1&&!a.variables)throw new Error(`Missing variables in style (expected ${Array.from(o.variables.keys())})`);for(const[n]of o.variables.entries()){if(!(n in a.variables))throw new Error(`Missing '${n}' in style variables`);const l=y(n);c[l]=function(){let f=a.variables[n];return typeof f=="string"&&(f=I(f)),f!==void 0?f:-9999999}}const d=Object.keys(c).map(function(n){return`uniform float ${n};`}),h=Math.ceil(e/4);if(d.push(`uniform sampler2D ${r.TILE_TEXTURE_ARRAY}[${h}];`),o.paletteTextures&&d.push(`uniform sampler2D ${x}[${o.paletteTextures.length}];`),t>0&&!("getBandValue"in o.functions)){let n="";for(let l=0;l<e;l++){const f=Math.floor(l/4);let T=l%4;l===e-1&&T===1&&(T=3);const S=`${r.TILE_TEXTURE_ARRAY}[${f}]`;n+=`  if (band == ${l+1}.0) {
    return texture2D(${S}, v_textureCoord + vec2(dx, dy))[${T}];
  }
`}o.functions.getBandValue=`float getBandValue(float band, float xOffset, float yOffset) {
  float dx = xOffset / ${r.TEXTURE_PIXEL_WIDTH};
  float dy = yOffset / ${r.TEXTURE_PIXEL_HEIGHT};
${n}
}`}const E=Object.keys(o.functions).map(function(n){return o.functions[n]}),p=`
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif

    varying vec2 v_textureCoord;
    varying vec2 v_localMapCoord;
    uniform vec4 ${r.RENDER_EXTENT};
    uniform float ${r.TRANSITION_ALPHA};
    uniform float ${r.TEXTURE_PIXEL_WIDTH};
    uniform float ${r.TEXTURE_PIXEL_HEIGHT};
    uniform float ${r.RESOLUTION};
    uniform float ${r.ZOOM};

    ${d.join(`
`)}

    ${E.join(`
`)}

    void main() {
      if (
        v_localMapCoord[0] < ${r.RENDER_EXTENT}[0] ||
        v_localMapCoord[1] < ${r.RENDER_EXTENT}[1] ||
        v_localMapCoord[0] > ${r.RENDER_EXTENT}[2] ||
        v_localMapCoord[1] > ${r.RENDER_EXTENT}[3]
      ) {
        discard;
      }

      vec4 color = texture2D(${r.TILE_TEXTURE_ARRAY}[0],  v_textureCoord);

      ${t&&a.color===void 0?`color.a = getBandValue(${t}.0, 0.0, 0.0);`:""}

      ${t?`if (getBandValue(${t}.0, 0.0, 0.0) == 0.0) { discard; }`:""}

      ${i.join(`
`)}

      gl_FragColor = color;
      gl_FragColor.rgb *= gl_FragColor.a;
      gl_FragColor *= ${r.TRANSITION_ALPHA};
    }`;return{vertexShader:s,fragmentShader:p,uniforms:c,paletteTextures:o.paletteTextures}}class X extends N{constructor(e){e=e?Object.assign({},e):{};const t=e.style||{};delete e.style,super(e),this.sources_=e.sources,this.renderedSource_=null,this.renderedResolution_=NaN,this.style_=t,this.styleVariables_=this.style_.variables||{},this.styleBandCount_=NaN,this.styleNodataBandIndex_=void 0,this.handleSourceUpdate_(),this.addChangeListener(v.SOURCE,this.handleSourceUpdate_)}getSources(e,t){const s=this.getSource();return this.sources_?typeof this.sources_=="function"?this.sources_(e,t):this.sources_:s?[s]:[]}getRenderSource(){return this.renderedSource_||this.getSource()}getSourceState(){const e=this.getRenderSource();return e?e.getState():"undefined"}handleSourceUpdate_(){this.hasRenderer()&&this.getRenderer().clearCache();const e=this.getSource();if(e)if(e.getState()==="loading"){const t=()=>{e.getState()==="ready"&&(e.removeEventListener("change",t),this.setStyle(this.style_))};e.addEventListener("change",t)}else this.setStyle(this.style_)}getFirstSource_(){const e=Number.MAX_SAFE_INTEGER,t=this.getSources([-e,-e,e,e],e);return t&&t.length?t[0]:null}usesCoverageBand_(e,t){if(!e||!t||e.hasAlpha!==!1)return!1;const s=e.getProjection();return!!s&&!R(s,t)}getSourceBandCount_(e){const t=this.getFirstSource_(),s=t&&"bandCount"in t?t.bandCount:4;return this.usesCoverageBand_(t,e)?s+1:s}getSourceNodataBandIndex_(e){const t=this.getFirstSource_();if(t)return this.usesCoverageBand_(t,e)?t.bandCount+1:"nodataBandIndex"in t?t.nodataBandIndex:void 0}parseStyleForRender_(e){const t=this.getSourceBandCount_(e),s=this.getSourceNodataBandIndex_(e);return this.styleBandCount_=t,this.styleNodataBandIndex_=s,L(this.style_,t,s)}applyShaders_(e){const t=this.parseStyleForRender_(e);this.getRenderer().reset({vertexShader:t.vertexShader,fragmentShader:t.fragmentShader,uniforms:t.uniforms,paletteTextures:t.paletteTextures})}createRenderer(){const e=this.getMapInternal()?.getView()?.getProjection(),t=this.parseStyleForRender_(e);return new $(this,{vertexShader:t.vertexShader,fragmentShader:t.fragmentShader,uniforms:t.uniforms,cacheSize:this.getCacheSize(),paletteTextures:t.paletteTextures})}renderSources(e,t){const s=this.getRenderer();let o;for(let i=0,c=t.length;i<c;++i)this.renderedSource_=t[i],s.prepareFrame(e)&&(o=s.renderFrame(e));return o}render(e,t){this.rendered=!0;const s=e.viewState;if(this.hasRenderer()){const u=s.projection;(this.getSourceBandCount_(u)!==this.styleBandCount_||this.getSourceNodataBandIndex_(u)!==this.styleNodataBandIndex_)&&this.applyShaders_(u)}const o=this.getSources(e.extent,s.resolution);let i=!0;for(let u=0,d=o.length;u<d;++u){const h=o[u],E=h.getState();if(E=="loading"){const p=()=>{h.getState()=="ready"&&(h.removeEventListener("change",p),this.changed())};h.addEventListener("change",p)}i=i&&E=="ready"}const c=this.renderSources(e,o);if(this.getRenderer().renderComplete&&i)return this.renderedResolution_=s.resolution,c;if(this.renderedResolution_>.5*s.resolution){const u=this.getSources(e.extent,this.renderedResolution_).filter(d=>!o.includes(d));if(u.length>0)return this.renderSources(e,u)}return c}setStyle(e){if(this.styleVariables_=e.variables||{},this.style_=e,this.hasRenderer()){const t=this.getMapInternal()?.getView()?.getProjection();this.applyShaders_(t),this.changed()}}updateStyleVariables(e){Object.assign(this.styleVariables_,e),this.changed()}}X.prototype.dispose;export{X as default};
//# sourceMappingURL=WebGLTile-6s1B7xiU.js.map
