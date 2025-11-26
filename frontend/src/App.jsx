import React, { useEffect, useState, useRef } from 'react'
import { io } from 'socket.io-client'
import * as PIXI from 'pixi.js'

// Connect to the same origin so the client uses the frontend host (nginx) as proxy for socket.io.
// Prefer websocket transport and fall back to polling if needed.
const socket = io(window.location.origin, { path: '/socket.io', transports: ['websocket','polling'] })

// diagnostic handlers for connection issues
socket.on('connect_error', (err) => { console.error('socket connect_error', err) })
socket.on('reconnect_error', (err) => { console.error('socket reconnect_error', err) })
socket.on('disconnect', (reason) => { console.warn('socket disconnected', reason) })

// Safe socket helpers: avoid calling .on/.off/.emit when socket is not a valid object
function safeOn(ev, handler){
  try{ if(socket && typeof socket.on === 'function') socket.on(ev, handler) }catch(e){ console.warn('safeOn failed', e) }
}
function safeOff(ev, handler){
  try{ if(socket && typeof socket.off === 'function') socket.off(ev, handler) }catch(e){ console.warn('safeOff failed', e) }
}
function safeEmit(...args){
  try{ if(socket && typeof socket.emit === 'function') socket.emit(...args) }catch(e){ console.warn('safeEmit failed', e) }
}

const TILE_SIZE = 48
const VIEWPORT_TILES_X = 16
const VIEWPORT_TILES_Y = 12

function makeTexture(color){
  const canvas = document.createElement('canvas')
  canvas.width = TILE_SIZE
  canvas.height = TILE_SIZE
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#'+(color>>>0).toString(16).padStart(6,'0')
  ctx.fillRect(0,0,TILE_SIZE,TILE_SIZE)
  ctx.strokeStyle = 'rgba(0,0,0,0.2)'
  ctx.lineWidth = 2
  ctx.strokeRect(1,1,TILE_SIZE-2,TILE_SIZE-2)
  return PIXI.Texture.from(canvas)
}

export default function App(){
  const [connected, setConnected] = useState(false)
  const [state, setState] = useState(null)
  const [player, setPlayer] = useState(null)
  const [joined, setJoined] = useState(false)
  const [hasStoredPlayer, setHasStoredPlayer] = useState(false)
  const [gamesExist, setGamesExist] = useState(false)
  const canvasRef = useRef(null)
  const appRef = useRef(null)
  const scaleRef = useRef(1)
  const animRef = useRef(null)
  const spriteClickRef = useRef(false)

  // helper to safely get the local stored playerId (available to component and effects)
  function getLocalPlayerId(){
    try{
      return sessionStorage.getItem('playerId') || (player && player.playerId) || null
    }catch(e){
      return (player && player.playerId) || null
    }
  }

  // helper to safely send actions only for the local browser's player
  function sendAction(action, gameIdOverride){
    const localId = getLocalPlayerId()
    const gid = gameIdOverride || (state && state.id) || (player && player.gameId)
    if(!localId || !gid) return
    // ensure local player exists in latest state
    const me = (state && state.players) ? state.players.find(pp => pp.id === localId) : null
    // allow respawn even if me is null or dead (respawn is allowed when dead)
    if(action && action.type !== 'respawn'){
      if(!me) return
      if(me.hp <= 0) return
    }
    safeEmit('action', {gameId: gid, playerId: localId, action})
  }

  useEffect(()=>{
    safeOn('connect', ()=> {
      setConnected(true)
      // On page reload, if we have a stored player, try to rejoin automatically
      try{
        const storedGameId = sessionStorage.getItem('gameId')
        const storedPlayerId = sessionStorage.getItem('playerId')
        if(storedGameId && storedPlayerId){
          // verify game still exists on server first; if not, clear stored session
          ;(async ()=>{
            try{
              const base = window.location.origin || 'http://localhost:5000'
              const r = await fetch(`${base}/api/games`)
              if(r.ok){
                const arr = await r.json()
                const exists = Array.isArray(arr) && arr.find(g => g.gameId === storedGameId)
                if(!exists){
                  try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
                  setHasStoredPlayer(false)
                  return
                }
              }
            }catch(e){/* ignore fetch errors and attempt join */}
            console.log('attempting automatic rejoin', storedGameId, storedPlayerId)
            safeEmit('join', {gameId: storedGameId, playerId: storedPlayerId}, (resp) => {
              if(resp && resp.error){
                console.warn('rejoin ack error', resp)
                const errMsg = String(resp.error || resp.message || '')
                if(errMsg.toLowerCase().includes('player_already')){
                  try{ alert('Le joueur stocké est déjà connecté ailleurs. Attendez la déconnexion ou utilisez "Effacer joueur stocké".') }catch(e){}
                } else if(errMsg.toLowerCase().includes('game not found')){
                  // clear stale stored session so UI returns to Join/Create state
                  try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
                  setHasStoredPlayer(false)
                } else {
                  try{ alert('Rejoin failed: ' + (resp.error || JSON.stringify(resp))) }catch(e){}
                }
              }
            })
          })()
        }
      }catch(e){ console.warn('automatic rejoin failed', e) }
    })
    safeOn('connected', d=> console.log('server', d))
    safeOn('state_update', s=> setState(s))
    // handle generic server errors (e.g. player already connected)
    // Do NOT auto-clear stored player on error; instead surface to user and rely on retry/clear button.
    safeOn('error', (err) => {
      try{
        const msg = err && (err.message || err.error || err.msg)
        console.warn('socket error', err)
        if(msg && String(msg).toLowerCase().includes('player already')){
          // server indicates this playerId is already connected elsewhere — inform user
          try{ alert('Le joueur stocké est déjà connecté ailleurs. Attente de la déconnexion ou utilisez "Effacer joueur stocké".') }catch(e){}
        }
        // if the server reports the game no longer exists, clear stored session so UI shows Join/Create
        if(msg && String(msg).toLowerCase().includes('game not found')){
          try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
          setHasStoredPlayer(false)
        }
      }catch(e){/* ignore */}
    })

    safeOn('joined', d=> {
      console.log('joined', d)
      // persist this browser's player identity so this tab/browser is tied to that player
      try{
        sessionStorage.setItem('gameId', d.gameId)
        sessionStorage.setItem('playerId', d.playerId)
        setHasStoredPlayer(true)
      }catch(e){/* ignore storage errors */}
      setPlayer(d)
      setJoined(true)
    })
    return ()=>{
      safeOff('connect')
      safeOff('connected')
      safeOff('state_update')
      safeOff('joined')
    }
  }, [])
  
  // Do not auto-create or auto-join on connect. Player creation/join happens only
  // when the user clicks the 'Join' button. Keep socket connected state in sync.
  useEffect(()=>{
    safeOn('connect', ()=> setConnected(true));
    // check if any games exist to decide button label
    ;(async function checkGames(){
      try{
        const r = await fetch(`${window.location.origin}/api/games`)
        if(r.ok){
          const arr = await r.json()
          setGamesExist(Array.isArray(arr) && arr.length > 0)
        }
      }catch(e){/* ignore */}
    })()
    return ()=>{
      safeOff('connect')
    }
  }, [])

  useEffect(()=>{
    try{
      setHasStoredPlayer(!!sessionStorage.getItem('playerId'))
    }catch(e){ setHasStoredPlayer(false) }
  }, [])

  useEffect(()=>{
    // init PIXI app
    const gridWidth = VIEWPORT_TILES_X * TILE_SIZE
    const gridHeight = VIEWPORT_TILES_Y * TILE_SIZE
    const app = new PIXI.Application({width: gridWidth, height: gridHeight, backgroundColor: 0x101010})
    appRef.current = app
    // append canvas
    const container = canvasRef.current
    container.innerHTML = ''
    container.appendChild(app.view)

    // create containers
    const tilesContainer = new PIXI.Container()
    const entitiesContainer = new PIXI.Container()
    const hudContainer = new PIXI.Container()
    app.stage.addChild(tilesContainer)
    app.stage.addChild(entitiesContainer)
    app.stage.addChild(hudContainer)

    // textures cache
    const textures = {
      floor: makeTexture(0x777777),
      wall: makeTexture(0x333333),
      monster: makeTexture(0xff0000)
    }

    const playerTextureCache = {}
    function getPlayerTexture(color){
      const c = color || 0x00ff00
      const key = String(c)
      if(!playerTextureCache[key]){
        playerTextureCache[key] = makeTexture(Number(c))
      }
      return playerTextureCache[key]
    }

    // animate stage scale smoothly from current to target over duration ms
    function animateStageScale(toScale, duration = 200){
      if(animRef.current) cancelAnimationFrame(animRef.current)
      const start = performance.now()
      const from = app.stage.scale.x || 1
      const diff = toScale - from
      function step(ts){
        const t = Math.min(1, (ts - start) / duration)
        // easeOutQuad
        const eased = 1 - (1 - t) * (1 - t)
        const cur = from + diff * eased
        app.stage.scale.set(cur, cur)
        scaleRef.current = cur
        if(t < 1){
          animRef.current = requestAnimationFrame(step)
        } else {
          animRef.current = null
        }
      }
      animRef.current = requestAnimationFrame(step)
    }

    // compute and apply responsive scale so the grid fills the container width
    function applyResponsive(){
      const rect = container.getBoundingClientRect()
      const containerWidth = rect.width || window.innerWidth
      const gridLogicalWidth = VIEWPORT_TILES_X * TILE_SIZE
      // target scale so grid fills container width; don't upscale beyond 1
      const target = Math.min(1, containerWidth / gridLogicalWidth)
      // set canvas css size to visual size
      const visualWidth = Math.round(gridLogicalWidth * target)
      const visualHeight = Math.round(gridLogicalWidth * target * (VIEWPORT_TILES_Y/VIEWPORT_TILES_X))
      app.view.style.width = visualWidth + 'px'
      app.view.style.height = visualHeight + 'px'
      // animate stage scale
      animateStageScale(target, 200)
    }

    // initial responsive
    applyResponsive()
    let raf = null
    const onResize = ()=>{
      if(raf) cancelAnimationFrame(raf)
      raf = requestAnimationFrame(()=> applyResponsive())
    }
    window.addEventListener('resize', onResize)

    function renderState(s){
      tilesContainer.removeChildren()
      entitiesContainer.removeChildren()
      hudContainer.removeChildren()
      if(!s || !s.map) return
      const rows = s.map.length
      const cols = s.map[0].length
      for(let y=0;y<rows;y++){
        for(let x=0;x<cols;x++){
          const tile = s.map[y][x]
          const tex = tile === 1 ? textures.wall : textures.floor
          const spr = new PIXI.Sprite(tex)
          // draw in logical coordinates; stage.scale handles visual scaling
          spr.x = x * TILE_SIZE
          spr.y = y * TILE_SIZE
          spr.width = TILE_SIZE
          spr.height = TILE_SIZE
          tilesContainer.addChild(spr)
        }
      }
      for(const p of s.players || []){
        const tex = getPlayerTexture(p.color)
        const spr = new PIXI.Sprite(tex)
        spr.x = p.position.x * TILE_SIZE
        spr.y = p.position.y * TILE_SIZE
        spr.width = TILE_SIZE
        spr.height = TILE_SIZE
        // show dead visuals
        spr.alpha = (p.hp <= 0) ? 0.6 : 1
        // make interactive so clicking a player triggers attack
        spr.interactive = true
        spr.buttonMode = true
        spr.on('pointerdown', (ev) => {
          // mark that a sprite was clicked so the underlying canvas click doesn't also move
          spriteClickRef.current = true
          // clear flag on next tick
          setTimeout(()=> { spriteClickRef.current = false }, 0)
          try{
            // find local player state
            const localId = (player && player.playerId) || null
            const me = (state && state.players) ? state.players.find(pp => pp.id === localId) : null
            if(!localId) return
            // dead players cannot act
            if(me && me.hp <= 0) return
            // clicking oneself does nothing
            if(p.id === localId) return
            // send attack action (helper enforces local ownership)
            sendAction({type: 'attack', targetId: p.id}, s.id)
          }catch(e){ /* ignore */ }
          // stop PIXI propagation
          try{ ev.stopPropagation && ev.stopPropagation() }catch(e){}
        })
        entitiesContainer.addChild(spr)

        // render dead cross overlay
        if(p.hp <= 0){
          const cross = new PIXI.Text('✗', {fontSize: 36, fill: 0xff0000, fontWeight: 'bold'})
          // center cross on tile
          cross.x = spr.x + TILE_SIZE/2 - (cross.width/2 || 0)
          cross.y = spr.y + TILE_SIZE/2 - (cross.height/2 || 0)
          entitiesContainer.addChild(cross)
        }
      }
      for(const m of s.monsters || []){
        const spr = new PIXI.Sprite(textures.monster)
        spr.x = m.position.x * TILE_SIZE
        spr.y = m.position.y * TILE_SIZE
        spr.width = TILE_SIZE
        spr.height = TILE_SIZE
        entitiesContainer.addChild(spr)
      }
      // Render HUD inside canvas: list all players, local player first
      if(s.players && s.players.length > 0){
        const controlsText = new PIXI.Text('Click on the grid to move your character or attack another player', {fontSize: 16, fill: 0xffffff})
        controlsText.x = 10
        controlsText.y = 10
        hudContainer.addChild(controlsText)

        // order players with local player first
        const playersList = (s.players || []).slice()
        if(player){
          const idx = playersList.findIndex(p => p.id === player.playerId)
          if(idx > 0){
            const me = playersList.splice(idx,1)[0]
            playersList.unshift(me)
          }
        }

        let stats = 'Players:\n'
        for(const p of playersList){
          const isMe = player && p.id === player.playerId
          stats += `${isMe ? '→ ' : '   '}${p.name}${isMe ? ' (You)' : ''}: HP ${p.hp}/${p.max_hp}, Pos (${p.position.x},${p.position.y}), Score: ${p.score || 0}\n`
        }
        stats += `Current Turn: ${s.current_turn ? ( (s.players.find(pp => pp.id === s.current_turn) || {}).name || 'Unknown') : 'None'}`
        const statsText = new PIXI.Text(stats, {fontSize: 14, fill: 0xffffff, lineHeight: 18})
        statsText.x = 10
        statsText.y = 40
        hudContainer.addChild(statsText)
      }
    }

    // initial render
    renderState(state)

    // listen for state changes to re-render
    const unsub = ()=>{}
    const updateHandler = (s)=> renderState(s)
    safeOn('state_update', updateHandler)

    // (sendAction and getLocalPlayerId moved to component scope)

    // click handling
    app.view.addEventListener('click', (ev)=>{
      if(!player || !state) return
      // if a sprite handled the pointer, skip the canvas grid move
      if(spriteClickRef.current){ spriteClickRef.current = false; return }
      // prevent dead local player from acting
      const me = (state.players || []).find(pp => pp.id === (player && player.playerId))
      if(me && me.hp <= 0) return
      const rect = app.view.getBoundingClientRect()
      const x = ev.clientX - rect.left
      const y = ev.clientY - rect.top
      const scale = scaleRef.current || 1
      // convert visual pixels back to logical pixels
      const logicalX = x / scale
      const logicalY = y / scale
      const gridX = Math.floor(logicalX / TILE_SIZE)
      const gridY = Math.floor(logicalY / TILE_SIZE)
      sendAction({type: 'move', x: gridX, y: gridY})
    })

    return ()=>{
      safeOff('state_update', updateHandler)
      window.removeEventListener('resize', onResize)
      if(animRef.current) cancelAnimationFrame(animRef.current)
      app.destroy(true, {children:true})
      appRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player, state])

  function clearStoredPlayer(){
    try{
      sessionStorage.removeItem('playerId')
      sessionStorage.removeItem('gameId')
    }catch(e){}
    setHasStoredPlayer(false)
    setPlayer(null)
    setJoined(false)
  }

  const join = async ()=>{
    console.log('join() clicked')
    try{
      // If this browser already has a stored playerId, try to rejoin that player instead
      try{
        const storedGameId = sessionStorage.getItem('gameId')
        const storedPlayerId = sessionStorage.getItem('playerId')
        if(storedGameId && storedPlayerId){
          // verify the referenced game still exists before attempting to rejoin
          const base = window.location.origin || 'http://localhost:5000'
          try{
            const r = await fetch(`${base}/api/games`)
            if(r.ok){
              const list = await r.json()
              const exists = Array.isArray(list) && list.find(g => g.gameId === storedGameId)
              if(!exists){
                try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
                setHasStoredPlayer(false)
                // continue to create/join flow below
              } else {
                console.log('reusing stored player', storedGameId, storedPlayerId)
                // try socket join; if server refuses, the ack handler will clear storage for player_already
                safeEmit('join', {gameId: storedGameId, playerId: storedPlayerId}, (resp) => {
                  if(resp && resp.error){
                    console.warn('join ack error', resp)
                    const errMsg = String(resp.error || resp.message || '')
                    if(errMsg.toLowerCase().includes('player_already')){
                      try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
                      setHasStoredPlayer(false)
                      // fall through to create a new player below (function will continue)
                    } else if(errMsg.toLowerCase().includes('game not found')){
                      try{ sessionStorage.removeItem('gameId'); sessionStorage.removeItem('playerId') }catch(e){}
                      setHasStoredPlayer(false)
                    }
                  }
                })
                return
              }
            }
          }catch(e){ console.warn('sessionStorage not available or games fetch failed', e) }
        }
      }catch(e){ console.warn('sessionStorage not available', e) }

      // Otherwise create a new game and join (use current origin to avoid CORS issues)
      const base = window.location.origin || 'http://localhost:5000'
      // If there are existing games, prefer joining the first one instead of creating a new game.
      if(gamesExist){
        const listResp = await fetch(`${base}/api/games`)
        if(listResp.ok){
          const list = await listResp.json()
          if(Array.isArray(list) && list.length > 0){
            const targetGameId = list[0].gameId
            const r = await fetch(`${base}/api/games/${targetGameId}/join`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})})
            if(!r.ok) throw new Error('join REST failed: ' + r.status)
            const pj = await r.json()
            console.log('joined existing game via REST', pj)
            safeEmit('join', {gameId: targetGameId, playerId: pj.playerId})
            return
          }
        }
      }
      const createResp = await fetch(`${base}/api/games`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name:'New Game', maxPlayers:4})})
      if(!createResp.ok) throw new Error('create game failed: ' + createResp.status)
      const newGame = await createResp.json()
      const r = await fetch(`${base}/api/games/${newGame.gameId}/join`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})})
      if(!r.ok) throw new Error('join REST failed: ' + r.status)
      const pj = await r.json()
      console.log('created and joined via REST', pj)
      safeEmit('join', {gameId: newGame.gameId, playerId: pj.playerId})
    }catch(err){
      console.error('join error', err)
      try{ alert('Join failed: ' + (err && err.message ? err.message : String(err))) }catch(e){}
    }
  }

  return (
    <div style={{padding:20}}>
      <h1>FunGame (frontend) - PixiJS</h1>
      <div>Socket connected: {String(connected)}</div>
      <button disabled={joined || hasStoredPlayer} title={hasStoredPlayer ? 'Player already stored in this browser' : ''} onClick={join}>
        {joined ? 'Joined' : (hasStoredPlayer ? 'Stored player' : (gamesExist ? 'Join Game' : 'Create Game'))}
      </button>
      {/* Respawn button: show when local stored player exists and is dead */}
      {(() => {
        try{
          const me = (state && state.players) ? state.players.find(p => p.id === (player && player.playerId)) : null
          if(me && me.hp <= 0){
            return (
              <button style={{marginLeft:12}} onClick={() => sendAction({type: 'respawn'})}>Respawn</button>
            )
          }
        }catch(e){/* ignore */}
        return null
      })()}
      <div ref={canvasRef} style={{border:'1px solid #ccc', width: VIEWPORT_TILES_X*TILE_SIZE, height: VIEWPORT_TILES_Y*TILE_SIZE, marginTop:10}} />
      {player && state && (
        <div style={{marginTop:10, border:'1px solid #ccc', padding:10, display:'inline-block'}}>
          <h3>Players</h3>
          {(() => {
            const playersList = (state.players || []).slice()
            if(player){
              const idx = playersList.findIndex(p => p.id === player.playerId)
              if(idx > 0){
                const me = playersList.splice(idx,1)[0]
                playersList.unshift(me)
              }
            }
            return playersList.map(p => (
              <div key={p.id} style={{display:'flex', alignItems:'center', marginBottom:6}}>
                <div style={{width:16, height:16, marginRight:8, backgroundColor: `#${(p.color>>>0).toString(16).padStart(6,'0')}`, border:'1px solid #000'}} />
                <div>
                  <div><strong>{p.name}{p.id === player.playerId ? ' (You)' : ''}</strong></div>
                  <div style={{fontSize:12}}>HP: {p.hp}/{p.max_hp} — Pos: ({p.position.x},{p.position.y}) — Score: {p.score || 0} — {state.current_turn === p.id ? 'Current turn' : 'Waiting'}</div>
                  {p.id === player.playerId && p.hp <= 0 && (
                    <div style={{marginTop:6}}>
                      <button onClick={() => sendAction({type: 'respawn'})}>Respawn</button>
                    </div>
                  )}
                </div>
              </div>
            ))
          })()}
        </div>
      )}
      <div style={{marginTop:10}}>
        <strong>State (debug):</strong>
        <pre style={{whiteSpace:'pre-wrap', maxHeight:200, overflow:'auto'}}>{state? JSON.stringify(state,null,2): 'no state yet'}</pre>
      </div>
    </div>
  )
}
