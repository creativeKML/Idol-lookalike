import { useState, useRef, useEffect } from 'react'
import './App.css'

const API = 'http://localhost:8000'

function App() {

  // 🔊 사운드
  const selectSoundRef = useRef(null)
  const fightSoundRef = useRef(null)
  const errorSoundRef = useRef(null)
  
  useEffect(() => {
    selectSoundRef.current = new Audio('/sounds/select.mp3')
    fightSoundRef.current  = new Audio('/sounds/fight.mp3')
    errorSoundRef.current  = new Audio('/sounds/error.mp3')
  }, [])
  
  // 겹침 방지 함수
  const playSound = (soundRef) => {
    if (!soundRef.current) return

    soundRef.current.currentTime = 0

    soundRef.current.play().catch(err => {
      console.log('🔇 sound error:', err)
    })
    soundRef.current.play()
  }  

  const [image, setImage] = useState(null)
  const [imageUrl, setImageUrl] = useState(null)
  const [gender, setGender] = useState('전체')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)

  const fileInputRef = useRef(null)

  useEffect(() => {
    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl)
    }
  }, [imageUrl])

  const handleFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return
    setImage(file)
    setImageUrl(URL.createObjectURL(file))
    setResults(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async () => {
    if (!image) return

    setLoading(true)
    setError(null)
    setResults(null)

    const formData = new FormData()
    formData.append('file', image)

    if (gender !== '전체') {
      formData.append('gender', gender === '여자' ? 'female' : 'male')
    }

    try {
      const res = await fetch(`${API}/api/match`, {
        method: 'POST',
        body: formData,
      })

      const data = await res.json()

      if (!res.ok) throw new Error(data.detail || data.message)

      if (!data.results || data.results.length === 0) {
        setError('닮은 연예인을 찾지 못했습니다.')
        return
      }

      setResults(data.results.slice(0, 3))
      setSelectedIdx(0)

    } catch (err) {
      playSound(errorSoundRef)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const formatName = (folder) => folder.split('_').slice(1).join(' ').toUpperCase()
  const groupName  = (folder) => folder.split('_')[0].toUpperCase()

  const selected = results?.[selectedIdx]

  return (
    <div className="game-root">

      {/* 타이틀 */}
      <div className="title-bar">
        <div className="title-deco">★</div>
        <h1 className="game-title">IDOL FIGHTER</h1>
        <div className="title-deco">★</div>
      </div>

      <div className="game-subtitle">— SELECT YOUR OPPONENT —</div>

      {/* VS */}
      <div className="vs-area">

        {/* 1P */}
        <div className="player-panel p1">

          <div className="player-label p1-label">1P</div>

          <div
            className={`portrait-frame ${dragging ? 'dragging' : ''}`}
            onClick={() => fileInputRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
          >
            {imageUrl ? (
              <img src={imageUrl} className="portrait-img" />
            ) : (
              <div className="portrait-empty">
                <div className="portrait-icon">📷</div>
                <div className="portrait-hint">DROP IMAGE</div>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              hidden
              onChange={(e) => {
                playSound(selectSoundRef)
                handleFile(e.target.files[0])
              }}
            />
          </div>

          <div className="player-name p1-name">YOU</div>

          <div className="gender-row">
            {['전체', '여자', '남자'].map((g) => (
              <button
                key={g}
                className={`gender-btn ${gender === g ? 'active' : ''}`}
                onClick={() => setGender(g)}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        {/* VS 중앙 */}
        <div className="vs-center">
          <div className="vs-text">VS</div>

          {selected && (
            <div className="similarity-display">
              <div className="sim-value">{selected.similarity}%</div>
              <div className="sim-label">MATCH</div>
            </div>
          )}
        </div>

        {/* 2P */}
        <div className="player-panel p2">

          <div className="player-label p2-label">2P</div>

          <div className="portrait-frame p2-frame">
            {selected ? (
              <img src={`${API}${selected.photo}`} className="portrait-img" />
            ) : (
              <div className="portrait-rival">
                <div className="rival-initial">?</div>
              </div>
            )}
          </div>

          <div className="player-name p2-name">
            {selected ? formatName(selected.folder) : '???'}
          </div>

          {selected && (
            <div className="player-group">
              {groupName(selected.folder)}
            </div>
          )}
        </div>

      </div>

      {/* 버튼 */}
      <div className="controls">
        <button
          className={`fight-btn ${loading ? 'loading' : ''}`}
          onClick={() => {
            playSound(fightSoundRef)
            handleSubmit()
          }}
          disabled={!image || loading}
        >
          {loading ? 'ANALYZING...' : 'FIGHT !'}
        </button>

        {error && <div className="error-msg">{error}</div>}
      </div>

      {/* TOP3 */}
      {results && (
        <div className="select-screen">

          <div className="select-title">▼ TOP MATCHES ▼</div>

          <div className="select-grid">
            {results.map((idol, i) => (
              <div
                key={idol.key}
                className={`
                select-card
                ${i === selectedIdx ? 'selected' : ''} 
                ${i === 0 ? 'winner' : ''}
                `}
                onClick={() => {
                  playSound(selectSoundRef)
                  setSelectedIdx(i)
                }}
              >
                {i === 0 && <div className="crown">👑</div>}

                <div className="select-avatar">
                  <img src={`${API}${idol.photo}`} className="select-avatar-img" />
                </div>

                <div className="select-name">
                  {formatName(idol.folder)}
                </div>

                <div className="select-sim">
                  {idol.similarity}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 푸터 */}
      <div className="footer-text">✦ INSERT COIN TO CONTINUE ✦</div>

      <div className="copyright">
        © <a href="https://github.com/creativeKML/Idol-lookalike" target="_blank">
          github.com/creativeKML/Idol-lookalike
        </a>
      </div>

    </div>
  )
}

export default App