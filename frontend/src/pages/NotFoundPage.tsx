import { useTranslation } from 'react-i18next'

export default function NotFoundPage() {
  const { t } = useTranslation()
  return <p>{t('notFound.message')}</p>
}
