import { useState, useRef } from 'react'
import './App.css'

const API = 'http://127.0.0.1:8000'

function App() {
  const [image, setImage] = useState(null)
  const [imageUrl, setImageUrl] = useState(null)
  const [gender, setGender] = useState('전체')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const fileInputRef = useRef(null)

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
    if (gender !== '전체') formData.append('gender', gender === '여자' ? 'female' : 'male')

    try {
      const res = await fetch(`${API}/api/match`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '오류가 발생했습니다.')
      setResults(data.results.slice(0, 3))
      setSelectedIdx(0)
    } catch (err) {
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
      <div className="scanlines" />

      {/* 타이틀 */}
      <div className="title-bar">
        <div className="title-deco">★</div>
        <h1 className="game-title">IDOL FIGHTER</h1>
        <div className="title-deco">★</div>
      </div>
      <p className="game-subtitle">— SELECT YOUR OPPONENT —</p>

      {/* VS 영역 */}
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
            {imageUrl
              ? <img src={imageUrl} alt="나" className="portrait-img" />
              : <div className="portrait-empty">
                  <span className="portrait-icon">👤</span>
                  <span className="portrait-hint">PRESS START</span>
                </div>
            }
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>
          <div className="player-name p1-name">YOU</div>

          {/* 성별 선택 - 1P 아래 */}
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
            {selected
              ? selected.photo
                ? <img src={`${API}${selected.photo}`} alt={formatName(selected.folder)} className="portrait-img" />
                : <div className="portrait-rival">
                    <span className="rival-initial">{formatName(selected.folder)[0]}</span>
                  </div>
              : <div className="portrait-empty">
                  <span className="portrait-icon">❓</span>
                  <span className="portrait-hint">???</span>
                </div>
            }
          </div>
          <div className="player-name p2-name">
            {selected ? formatName(selected.folder) : '???'}
          </div>
          {selected && (
            <div className="player-group">{groupName(selected.folder)}</div>
          )}
        </div>
      </div>

      {/* FIGHT 버튼 */}
      <div className="controls">
        <button
          className={`fight-btn ${loading ? 'loading' : ''}`}
          onClick={handleSubmit}
          disabled={!image || loading}
        >
          {loading ? 'ANALYZING...' : '▶  FIGHT !'}
        </button>
        {error && <p className="error-msg">⚠ {error}</p>}
      </div>

      {/* 캐릭터 선택창 */}
      {results && (
        <div className="select-screen">
          <div className="select-title">▼ TOP MATCHES ▼</div>
          <div className="select-grid">
            {results.map((idol, i) => (
              <div
                key={idol.key}
                className={`select-card ${selectedIdx === i ? 'selected' : ''}`}
                onClick={() => setSelectedIdx(i)}
              >
                <div className="select-rank">#{i + 1}</div>
                <div className="select-avatar">
                  {idol.photo
                    ? <img src={`${API}${idol.photo}`} alt={formatName(idol.folder)} className="select-avatar-img" />
                    : formatName(idol.folder)[0]
                  }
                </div>
                <div className="select-name">{formatName(idol.folder)}</div>
                <div className="select-sim">{idol.similarity}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="footer-text">✦ INSERT COIN TO CONTINUE ✦</div>
    </div>
  )
}

export default App
