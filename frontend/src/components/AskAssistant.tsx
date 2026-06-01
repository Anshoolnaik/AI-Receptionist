import { useState, FormEvent } from 'react'
import { api, AskResponse } from '../api/client'

interface Props { propertyId: string }

export default function AskAssistant({ propertyId }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.ask(propertyId, question.trim())
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <form className="ask-form" onSubmit={submit}>
        <textarea
          className="ask-textarea"
          placeholder="Koi bhi sawaal poochein… (Ask anything about your property data or product help)"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          disabled={loading}
        />
        <button className="ask-btn" type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Thinking…' : 'Ask →'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="ask-result">
          {result.refused ? (
            <div className="ask-refused">
              ⚠️ {result.note ?? 'This question could not be answered. Please rephrase or contact support.'}
            </div>
          ) : (
            <div className="ask-answer">{result.answer}</div>
          )}

          {result.source && (
            <p className="ask-source">📄 Source: {result.source}</p>
          )}

          {result.sql && (
            <div>
              <p className="sql-label">SQL ran:</p>
              <pre className="sql-block">{result.sql}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
